from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import re
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.db import (
    IntegrityError,
    OperationalError,
    close_old_connections,
    transaction,
)
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.utils import timezone
from .models import OwnerState, AdminChallenge, ApprovedAdministrator
from . import owner_security as auth

OPTIONS = dict(
    OWNER_EMAIL="verified.owner@gmail.com",
    ADMIN_SETUP_SECRET="test-only-setup-secret-" + "x" * 40,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="FarmCart <verified@example.test>",
    EMAIL_API_KEY="",
    OWNER_AUTH_DURABLE=True,
    OWNER_AUTH_TEST_MODE=True,
)
PASSWORD = "FarmOwner!3A8xf619"


class AuthHelpers:
    def issue(self, purpose="setup", username="umid_w", **extra):
        return auth.issue(
            purpose,
            username=username,
            password=PASSWORD,
            binding="test-binding",
            source="test-source",
            setup_secret=settings.ADMIN_SETUP_SECRET,
            **extra,
        )

    def code(self):
        return re.search(r"Verification code: (\d{8})", mail.outbox[-1].body).group(1)

    def owner(self):
        result = self.issue()
        self.assertTrue(result.ok, result.error)
        code = self.code()
        result = auth.verify(result.challenge.pk, code, "test-binding")
        self.assertTrue(result.ok, result.error)
        return result.user


@override_settings(**OPTIONS)
class OwnerSecurityTests(AuthHelpers, TestCase):
    def test_secret_required_recipient_fixed_no_active_account_until_verified(self):
        result = auth.issue(
            "setup",
            username="intruder",
            password=PASSWORD,
            binding="b",
            source="ip",
            setup_secret="wrong",
        )
        self.assertFalse(result.ok)
        self.assertFalse(User.objects.filter(is_staff=True).exists())
        self.assertEqual(len(mail.outbox), 0)
        result = self.issue()
        code = self.code()
        self.assertEqual(mail.outbox[0].to, ["verified.owner@gmail.com"])
        self.assertFalse(User.objects.filter(username="umid_w").exists())
        challenge = AdminChallenge.objects.get(pk=result.challenge.pk)
        self.assertNotIn(code, challenge.code_digest)
        self.assertNotIn(PASSWORD, challenge.password_hash)
        result = auth.verify(challenge.pk, code, "test-binding")
        self.assertTrue(result.ok)
        self.assertTrue(result.user.check_password(PASSWORD))
        self.assertTrue(result.user.is_superuser)
        self.assertEqual(
            OwnerState.objects.get().verified_email, "verified.owner@gmail.com"
        )
        self.assertFalse(auth.verify(challenge.pk, code, "test-binding").ok)

    def test_expiration_and_max_attempts_persist(self):
        result = self.issue()
        code = self.code()
        for _ in range(5):
            self.assertFalse(auth.verify(result.challenge.pk, "bad", "test-binding").ok)
        self.assertFalse(auth.verify(result.challenge.pk, code, "test-binding").ok)
        result = self.issue(username="another")
        code = self.code()
        AdminChallenge.objects.filter(pk=result.challenge.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertFalse(auth.verify(result.challenge.pk, code, "test-binding").ok)
        self.assertFalse(User.objects.exists())

    def test_wrong_binding_cannot_verify(self):
        result = self.issue()
        self.assertFalse(
            auth.verify(result.challenge.pk, self.code(), "other-browser").ok
        )

    def test_setup_closed_permanently_and_one_state_constraint(self):
        self.owner()
        self.assertFalse(self.issue(username="second_owner").ok)
        self.assertEqual(self.client.get("/admin/setup/").status_code, 404)
        self.assertEqual(self.client.post("/admin/setup/", {}).status_code, 404)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OwnerState.objects.create(pk=2)

    def test_fresh_owner_password_required_and_only_owner_can_invite(self):
        owner = self.owner()
        customer = User.objects.create_user("customer", password=PASSWORD)
        self.assertFalse(
            self.issue("invite", "extra", actor=customer, owner_password=PASSWORD).ok
        )
        self.assertFalse(
            self.issue("invite", "extra", actor=owner, owner_password="incorrect").ok
        )
        count = len(mail.outbox)
        self.assertEqual(count, 1)
        result = self.issue("invite", "extra", actor=owner, owner_password=PASSWORD)
        code = self.code()
        self.assertEqual(mail.outbox[-1].to, [settings.OWNER_EMAIL])
        self.assertFalse(User.objects.filter(username="extra").exists())
        self.assertFalse(
            auth.verify(result.challenge.pk, code, "test-binding", actor=customer).ok
        )
        result = self.issue("invite", "extra", actor=owner, owner_password=PASSWORD)
        result = auth.verify(
            result.challenge.pk, self.code(), "test-binding", actor=owner
        )
        self.assertTrue(result.ok)
        self.assertTrue(auth.is_administrator(result.user))
        self.assertFalse(result.user.is_superuser)
        self.assertTrue(
            ApprovedAdministrator.objects.filter(
                user=result.user, approved_by=owner
            ).exists()
        )
        self.assertFalse(result.user.has_perm("auth.add_user"))

    def test_customer_role_injection_and_admin_backend_permissions(self):
        owner = self.owner()
        self.client.post(
            "/register/",
            {
                "username": "customer",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        customer = User.objects.get(username="customer")
        self.assertFalse(customer.is_staff)
        self.client.post(
            "/account/",
            {"email": "customer@example.test", "is_superuser": "1", "is_staff": "1"},
        )
        customer.refresh_from_db()
        self.assertFalse(customer.is_staff)
        self.assertEqual(
            self.client.post("/admin/owner/administrators/", {}).status_code, 403
        )
        self.assertEqual(self.client.post("/admin/auth/user/add/", {}).status_code, 302)
        self.client.force_login(owner)
        self.assertEqual(
            self.client.post(
                "/admin/auth/user/add/", {"username": "bypass", "is_staff": "on"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                f"/admin/auth/user/{customer.pk}/change/", {"is_superuser": "on"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/admin/auth/group/add/", {}).status_code, 404
        )
        self.assertFalse(User.objects.filter(username="bypass").exists())
        self.assertContains(self.client.get("/admin/"), "Əlavə administrator yarat")

    def test_unapproved_superuser_cannot_login_or_access_admin(self):
        User.objects.create_superuser("unapproved", "", PASSWORD)
        response = self.client.post(
            "/admin/login/", {"username": "unapproved", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_owner_login_and_state_survive_new_session_connection(self):
        owner = self.owner()
        close_old_connections()
        client = Client()
        response = client.post(
            "/admin/login/", {"username": owner.username, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get("/admin/").status_code, 200)
        self.assertTrue(OwnerState.objects.get(pk=1).closed)

    def test_recovery_generic_and_single_use_owner_only_destination(self):
        owner = self.owner()
        unknown = self.client.post(
            "/admin/recover/",
            {
                "username": "unknown",
                "password1": "NewSafePass!90214",
                "password2": "NewSafePass!90214",
            },
        )
        known = self.client.post(
            "/admin/recover/",
            {
                "username": owner.username,
                "password1": "NewSafePass!90214",
                "password2": "NewSafePass!90214",
            },
        )
        self.assertEqual(unknown.status_code, known.status_code)
        self.assertEqual(unknown.url, known.url)
        pending = self.client.session["admin_verification"]
        code = self.code()
        self.assertEqual(mail.outbox[-1].to, [settings.OWNER_EMAIL])
        response = self.client.post("/admin/verify/", {"code": code, "approve": "on"})
        self.assertEqual(response.status_code, 302)
        owner.refresh_from_db()
        self.assertTrue(owner.check_password("NewSafePass!90214"))
        self.assertFalse(auth.verify(pending["id"], code, pending["binding"]).ok)

    def test_password_change_and_email_reconfiguration_invalidate_pending_approval(
        self,
    ):
        owner = self.owner()
        result = self.issue("invite", "extra", actor=owner, owner_password=PASSWORD)
        code = self.code()
        owner.set_password("ChangedOwner!28713")
        owner.save()
        self.assertFalse(
            auth.verify(result.challenge.pk, code, "test-binding", actor=owner).ok
        )
        with override_settings(OWNER_EMAIL="other@gmail.com"):
            self.assertFalse(
                self.issue(
                    "invite", "extra", actor=owner, owner_password="ChangedOwner!28713"
                ).ok
            )

    def test_delivery_failure_never_creates_admin_and_no_console_fallback(self):
        with patch(
            "shop.owner_security.send_mail",
            side_effect=RuntimeError("provider secret details"),
        ):
            result = self.issue()
            self.assertFalse(result.ok)
            self.assertNotIn("provider", result.error)
        self.assertFalse(User.objects.exists())
        self.assertTrue(AdminChallenge.objects.get().consumed)
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
        ):
            self.assertFalse(auth.configured())

    def test_mail_and_login_limits_are_database_backed(self):
        for index in range(3):
            self.assertTrue(self.issue(username=f"owner{index}").ok)
        self.assertFalse(self.issue(username="owner4").ok)
        self.assertEqual(len(mail.outbox), 3)
        for _ in range(10):
            self.assertTrue(auth.login_allowed("ip", "account"))
        self.assertFalse(auth.login_allowed("ip", "account"))
        close_old_connections()
        self.assertFalse(auth.login_allowed("ip", "account"))

    def test_ephemeral_storage_fails_closed_and_csrf_enforced(self):
        with override_settings(OWNER_AUTH_DURABLE=False):
            self.assertFalse(self.issue().ok)
            self.assertEqual(len(mail.outbox), 0)
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post("/admin/setup/", {}).status_code, 403)
        self.assertEqual(c.post("/admin/verify/", {}).status_code, 403)

    def test_web_setup_does_not_echo_code_and_rejects_recipient_override(self):
        response = self.client.post(
            "/admin/setup/",
            {
                "username": "umid_w",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "setup_secret": settings.ADMIN_SETUP_SECRET,
                "email": "attacker@example.test",
            },
        )
        self.assertEqual(response.status_code, 302)
        code = self.code()
        self.assertEqual(mail.outbox[-1].to, [settings.OWNER_EMAIL])
        self.assertNotContains(self.client.get("/admin/verify/"), code)
        self.assertEqual(
            self.client.post(
                "/admin/verify/", {"code": code, "approve": "on"}
            ).status_code,
            302,
        )
        self.assertEqual(self.client.get("/admin/setup/").status_code, 404)


@override_settings(**OPTIONS)
class ConcurrentOwnerTests(AuthHelpers, TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        OwnerState.objects.get_or_create(pk=1)

    def test_two_simultaneous_verifications_create_one_owner(self):
        from django.contrib.auth.hashers import make_password

        first = self.issue()
        code = self.code()
        second = AdminChallenge(
            purpose="setup",
            username="other_owner",
            password_hash=make_password(PASSWORD),
            binding_digest=auth.digest("test-binding"),
            recipient_digest=auth.digest(settings.OWNER_EMAIL),
            authorization_digest=auth.digest(settings.ADMIN_SETUP_SECRET),
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        second.code_digest = auth.digest(f"{second.pk}:{code}")
        second.save()
        from threading import Barrier

        barrier = Barrier(2)

        def worker(pk):
            close_old_connections()
            barrier.wait()
            try:
                return auth.verify(pk, code, "test-binding").ok
            except OperationalError:
                return False  # SQLite may report contention; HTTP wrapper returns 503.
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, [first.challenge.pk, second.pk]))
        self.assertEqual(sum(results), 1)
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
        self.assertTrue(OwnerState.objects.get(pk=1).closed)


@override_settings(**OPTIONS)
class OwnerRevocationTests(AuthHelpers, TestCase):
    def test_owner_can_revoke_additional_admin_with_fresh_password(self):
        owner = self.owner()
        result = self.issue("invite", "extra", actor=owner, owner_password=PASSWORD)
        member = auth.verify(
            result.challenge.pk, self.code(), "test-binding", actor=owner
        ).user
        membership = ApprovedAdministrator.objects.get(user=member)
        self.assertFalse(auth.revoke(member, PASSWORD, membership.pk).ok)
        self.assertFalse(auth.revoke(owner, "wrong", membership.pk).ok)
        self.assertTrue(auth.revoke(owner, PASSWORD, membership.pk).ok)
        member.refresh_from_db()
        self.assertFalse(auth.is_administrator(member))
        self.assertFalse(member.is_staff)


@override_settings(**OPTIONS)
class AdditionalSecurityTests(AuthHelpers, TestCase):
    def test_setup_key_rotation_revokes_pending_code_and_wrong_code_not_reflected(self):
        result = self.issue()
        code = self.code()
        with override_settings(ADMIN_SETUP_SECRET="new-deployment-secret-" + "y" * 40):
            self.assertFalse(auth.verify(result.challenge.pk, code, "test-binding").ok)
        session = self.client.session
        session["admin_verification"] = {
            "id": str(result.challenge.pk),
            "binding": "test-binding",
        }
        session.save()
        response = self.client.post("/admin/verify/", {"code": code, "approve": "on"})
        self.assertNotContains(response, code)

    def test_email_backend_rejects_recipient_override_before_network(self):
        from django.core.mail import EmailMessage
        from .email_backend import ResendBackend, EmailDeliveryError

        with (
            override_settings(EMAIL_API_KEY="test-key"),
            patch("shop.email_backend.urlopen") as network,
        ):
            with self.assertRaises(EmailDeliveryError):
                ResendBackend().send_messages(
                    [
                        EmailMessage(
                            "Subject",
                            "Body",
                            settings.DEFAULT_FROM_EMAIL,
                            ["attacker@example.test"],
                        )
                    ]
                )
            network.assert_not_called()

    def test_new_setup_code_invalidates_old_and_weak_password_is_rejected(self):
        first = self.issue()
        old_code = self.code()
        second = self.issue(username="newowner")
        new_code = self.code()
        self.assertFalse(auth.verify(first.challenge.pk, old_code, "test-binding").ok)
        self.assertTrue(auth.verify(second.challenge.pk, new_code, "test-binding").ok)
        count = len(mail.outbox)
        weak = auth.issue(
            "invite",
            username="weakadmin",
            password="12345678",
            binding="b",
            source="ip",
            actor=User.objects.get(username="newowner"),
            owner_password=PASSWORD,
        )
        self.assertFalse(weak.ok)
        self.assertEqual(len(mail.outbox), count)
