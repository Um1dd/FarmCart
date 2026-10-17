"""Owner approval state machine. All transitions serialize on a singleton DB row.

The UPDATE obtains a write lock before reading (also on SQLite); the primary-key
constraint and transaction ensure only one initial owner can ever be activated.
Expected failures return normally so attempt counters are committed, not rolled back.
"""

from dataclasses import dataclass
from datetime import timedelta
import re
import secrets
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import User, Permission
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.debug import sensitive_variables
from .models import OwnerState, ApprovedAdministrator, AdminChallenge, SecurityThrottle


@dataclass
class Result:
    ok: bool
    error: str = ""
    challenge: object = None
    user: object = None


class SecurityStateUnavailable(RuntimeError):
    pass


ERROR = "Müraciət təsdiqlənmədi. Məlumatları yoxlayın və ya bir qədər sonra yenidən cəhd edin."


def digest(value):
    return salted_hmac(
        "farmcart-owner-auth-v1", str(value), algorithm="sha256"
    ).hexdigest()


def owner_email():
    try:
        validate_email(settings.OWNER_EMAIL)
    except ValidationError:
        return ""
    return settings.OWNER_EMAIL if settings.OWNER_EMAIL.endswith("@gmail.com") else ""


def configured():
    backend = settings.EMAIL_BACKEND
    delivery = (
        backend == "shop.email_backend.ResendBackend"
        and settings.EMAIL_API_KEY
        and settings.DEFAULT_FROM_EMAIL
    )
    delivery = delivery or (
        settings.OWNER_AUTH_TEST_MODE
        and backend == "django.core.mail.backends.locmem.EmailBackend"
    )
    return bool(owner_email() and delivery and settings.OWNER_AUTH_DURABLE)


def state_locked():
    # Row is installed by migration; never silently recreate lost security state.
    if not OwnerState.objects.filter(pk=1).update(revision=F("revision") + 1):
        raise SecurityStateUnavailable(
            "Owner security state is missing; run migrations."
        )
    return OwnerState.objects.select_for_update().get(pk=1)


def throttle(key, limit, seconds):
    key = digest(key)
    now = timezone.now()
    row, _ = SecurityThrottle.objects.get_or_create(
        key=key, defaults={"window_start": now}
    )
    if row.window_start <= now - timedelta(seconds=seconds):
        row.window_start, row.count = now, 0
    row.count += 1
    row.save(update_fields=["window_start", "count"])
    return row.count <= limit


def is_owner(user):
    return bool(
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and OwnerState.objects.filter(pk=1, owner_id=user.pk, closed=True).exists()
    )


def is_administrator(user):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return False
    return is_owner(user) or (
        OwnerState.objects.filter(pk=1, closed=True).exists()
        and ApprovedAdministrator.objects.filter(user=user).exists()
    )


def fresh_owner(user, password, state):
    return bool(
        state.closed
        and user
        and user.is_authenticated
        and user.pk == state.owner_id
        and state.owner.is_active
        and state.owner.is_staff
        and state.owner.check_password(password)
    )


def login_allowed(source, username):
    with transaction.atomic():
        state_locked()
        a = throttle("login-source:" + source, 40, 900)
        if not a:
            return False
        return throttle("login-user:" + username.casefold(), 10, 900)


@sensitive_variables()
def issue(
    purpose,
    *,
    username,
    password,
    binding,
    source,
    setup_secret="",
    actor=None,
    owner_password="",
):
    with transaction.atomic():
        state = state_locked()
        if not throttle("request:" + purpose + ":" + source, 10, 900):
            return Result(
                False, "Sorğu limiti dolub. 15 dəqiqə sonra yenidən cəhd edin."
            )
        if not configured():
            return Result(
                False, "Təhlükəsiz e-poçt və qalıcı baza konfiqurasiyası tamamlanmayıb."
            )
        if purpose == "setup":
            valid_secret = len(
                settings.ADMIN_SETUP_SECRET
            ) >= 32 and constant_time_compare(setup_secret, settings.ADMIN_SETUP_SECRET)
            if state.closed or state.owner_id or not valid_secret:
                return Result(False, ERROR)
        elif purpose == "invite":
            if state.verified_email != owner_email():
                return Result(False, ERROR)
            if not state.closed or not fresh_owner(actor, owner_password, state):
                return Result(False, ERROR)
        elif purpose == "recover":
            if state.verified_email != owner_email():
                return Result(False, ERROR)
            if not state.closed or not state.owner_id:
                return Result(False, ERROR)
            target = User.objects.filter(
                username=username, is_active=True, is_staff=True
            ).first()
            if not target or not (
                target.pk == state.owner_id
                or ApprovedAdministrator.objects.filter(user=target).exists()
            ):
                return Result(False, ERROR)
        else:
            return Result(False, ERROR)
        try:
            User._meta.get_field("username").clean(username, None)
            validate_password(password, User(username=username))
        except ValidationError:
            return Result(False, ERROR)
        if (
            purpose != "recover"
            and User.objects.filter(username__iexact=username).exists()
        ):
            # Only a setup-secret holder or freshly authenticated owner reaches this point.
            return Result(
                False,
                "Bu istifadəçi adı artıq istifadə olunur. Mövcud müştəri hesabına admin hüququ verilmir; başqa admin adı seçin.",
            )
        # Global limits prevent changing IP/session to send arbitrary amounts of mail.
        if not throttle("delivery:" + purpose, 3, 3600):
            return Result(
                False,
                "E-poçt göndərişi limiti dolub: saatda maksimum 3 cəhd. 1 saatlıq limit bitdikdən sonra yenidən cəhd edin.",
            )
        # Keep one outstanding operation of each type, invalidating older codes.
        AdminChallenge.objects.filter(purpose=purpose, consumed=False).update(
            consumed=True, password_hash=""
        )
        challenge = AdminChallenge(
            purpose=purpose,
            username=username,
            password_hash=make_password(password),
            binding_digest=digest(binding),
            recipient_digest=digest(owner_email()),
            requested_by=actor if purpose == "invite" else None,
            authorization_digest=digest(settings.ADMIN_SETUP_SECRET)
            if purpose == "setup"
            else digest(state.owner.password),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        code = f"{secrets.randbelow(100_000_000):08d}"
        challenge.code_digest = digest(f"{challenge.id}:{code}")
        challenge.save()
        labels = {
            "setup": "Initial owner setup",
            "invite": "Additional administrator approval",
            "recover": "Administrator password recovery",
        }
        body = (
            f"FarmCart — {labels[purpose]}\nAccount: {username}\n\nVerification code: {code}\n\n"
            "This code expires in 10 minutes and can be used once. "
            "Enter it only on your FarmCart verification page. "
            "If you did not initiate this request, ignore this email. Never share this code."
        )
        try:
            sent = send_mail(
                "FarmCart — " + labels[purpose],
                body,
                settings.DEFAULT_FROM_EMAIL,
                [owner_email()],
                fail_silently=False,
            )
            if sent != 1:
                raise RuntimeError("Delivery failed")
        except Exception:
            challenge.consumed, challenge.password_hash = True, ""
            challenge.save(update_fields=["consumed", "password_hash"])
            return Result(
                False,
                "E-poçt göndərilmədi. Serverin e-poçt konfiqurasiyasını yoxlayın.",
            )
        return Result(True, challenge=challenge)


@sensitive_variables()
def verify(challenge_id, code, binding, *, actor=None):
    with transaction.atomic():
        state = state_locked()
        challenge = (
            AdminChallenge.objects.select_for_update().filter(pk=challenge_id).first()
        )
        if not challenge or not constant_time_compare(
            challenge.binding_digest, digest(binding)
        ):
            return Result(False, ERROR)
        if (
            challenge.consumed
            or challenge.expires_at <= timezone.now()
            or challenge.attempts >= 5
        ):
            challenge.consumed, challenge.password_hash = True, ""
            challenge.save(update_fields=["consumed", "password_hash"])
            return Result(False, ERROR)
        challenge.attempts += 1
        valid = bool(
            re.fullmatch(r"\d{8}", code)
            and constant_time_compare(
                challenge.code_digest, digest(f"{challenge.id}:{code}")
            )
        )
        if not valid:
            if challenge.attempts >= 5:
                challenge.consumed, challenge.password_hash = True, ""
            challenge.save(update_fields=["attempts", "consumed", "password_hash"])
            return Result(False, ERROR)
        # Configuration changes invalidate already-issued codes, including owner mail changes.
        permitted = configured() and constant_time_compare(
            challenge.recipient_digest, digest(owner_email())
        )
        if challenge.purpose == "setup":
            permitted = (
                permitted
                and not state.closed
                and not state.owner_id
                and len(settings.ADMIN_SETUP_SECRET) >= 32
                and constant_time_compare(
                    challenge.authorization_digest, digest(settings.ADMIN_SETUP_SECRET)
                )
            )
        else:
            permitted = (
                permitted
                and state.closed
                and state.owner_id
                and state.owner.is_active
                and state.owner.is_staff
                and state.verified_email == owner_email()
                and constant_time_compare(
                    challenge.authorization_digest, digest(state.owner.password)
                )
            )
            if challenge.purpose == "invite":
                permitted = (
                    permitted
                    and actor
                    and actor.is_authenticated
                    and actor.pk == state.owner_id
                    and actor.pk == challenge.requested_by_id
                    and actor.is_active
                    and actor.is_staff
                )
        if (
            challenge.purpose != "recover"
            and User.objects.filter(username__iexact=challenge.username).exists()
        ):
            permitted = False
        if not permitted:
            challenge.consumed, challenge.password_hash = True, ""
            challenge.save(update_fields=["consumed", "password_hash"])
            return Result(False, ERROR)
        if challenge.purpose == "recover":
            user = User.objects.filter(
                username=challenge.username, is_active=True, is_staff=True
            ).first()
            if not user or not (
                user.pk == state.owner_id
                or ApprovedAdministrator.objects.filter(user=user).exists()
            ):
                challenge.consumed, challenge.password_hash = True, ""
                challenge.save(update_fields=["attempts", "consumed", "password_hash"])
                return Result(False, ERROR)
            user.password = challenge.password_hash
            user.save(update_fields=["password"])
        else:
            user = User(
                username=challenge.username,
                password=challenge.password_hash,
                email=owner_email() if challenge.purpose == "setup" else "",
                is_active=True,
                is_staff=True,
                is_superuser=challenge.purpose == "setup",
            )
            try:
                with transaction.atomic():
                    user.save(force_insert=True)
            except IntegrityError:
                challenge.consumed, challenge.password_hash = True, ""
                challenge.save(update_fields=["attempts", "consumed", "password_hash"])
                return Result(False, ERROR)
            if challenge.purpose == "setup":
                state.owner, state.closed, state.verified_email = (
                    user,
                    True,
                    owner_email(),
                )
                state.save(update_fields=["owner", "closed", "verified_email"])
            else:
                ApprovedAdministrator.objects.create(user=user, approved_by=state.owner)
                user.user_permissions.set(
                    Permission.objects.filter(
                        content_type__app_label="shop",
                        content_type__model__in=[
                            "product",
                            "productvariant",
                            "region",
                            "category",
                            "video",
                            "storesettings",
                        ],
                    )
                )
        challenge.consumed, challenge.password_hash = True, ""
        challenge.save(update_fields=["attempts", "consumed", "password_hash"])
        # A successful state change cancels every other pending security operation.
        AdminChallenge.objects.filter(consumed=False).update(
            consumed=True, password_hash=""
        )
        return Result(True, user=user)


@sensitive_variables()
def revoke(actor, password, membership_id):
    with transaction.atomic():
        state = state_locked()
        if not throttle("revoke-owner", 10, 900) or not fresh_owner(
            actor, password, state
        ):
            return Result(False, ERROR)
        member = (
            ApprovedAdministrator.objects.filter(pk=membership_id)
            .select_related("user")
            .first()
        )
        if not member or member.user_id == state.owner_id:
            return Result(False, ERROR)
        member.user.is_staff = False
        member.user.save(update_fields=["is_staff"])
        member.user.user_permissions.clear()
        member.delete()
        return Result(True)
