import secrets
from functools import wraps
from django.contrib import messages
from django.contrib.auth import logout
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.db import OperationalError
from .models import OwnerState, ApprovedAdministrator
from .owner_forms import SetupForm, InviteForm, AdminCredentialsForm, VerificationForm
from . import owner_security as security


def protected_response(view):
    @wraps(view)
    @never_cache
    @sensitive_post_parameters()
    @require_http_methods(["GET", "POST"])
    def wrapped(request, *args, **kwargs):
        try:
            response = view(request, *args, **kwargs)
        except (OperationalError, security.SecurityStateUnavailable):
            # SQLite contention must fail closed; never reveal DB details.
            return render(
                request,
                "shop/owner_auth.html",
                {"heading": "Admin təhlükəsizliyi", "error": security.ERROR},
                status=503,
            )
        response["Referrer-Policy"] = "same-origin"
        return response

    return wrapped


def operation(request, purpose):
    state = OwnerState.objects.get(pk=1)
    if purpose == "setup" and (state.closed or state.owner_id):
        raise Http404
    if purpose == "invite" and not security.is_owner(request.user):
        return HttpResponseForbidden("İcazə yoxdur.")
    if (
        purpose == "invite"
        and request.method == "POST"
        and request.POST.get("action") == "revoke"
    ):
        member_id = request.POST.get("membership", "")
        if not member_id.isdigit() or request.POST.get("confirm") != "on":
            return HttpResponseForbidden("İcazə yoxdur.")
        result = security.revoke(
            request.user, request.POST.get("owner_password", "")[:256], int(member_id)
        )
        messages.success(
            request, "Administrator icazəsi ləğv edildi."
        ) if result.ok else messages.error(request, security.ERROR)
        return redirect("/admin/owner/administrators/")
    if purpose == "setup" and not security.configured():
        return render(
            request,
            "shop/owner_auth.html",
            {
                "heading": "Admin quraşdırılması",
                "error": "Təhlükəsiz e-poçt və qalıcı baza konfiqurasiyası tamamlanmayıb.",
            },
            status=503,
        )
    form_type = {
        "setup": SetupForm,
        "invite": InviteForm,
        "recover": AdminCredentialsForm,
    }[purpose]
    heading = {
        "setup": "İlk sahib hesabının quraşdırılması",
        "invite": "Əlavə administrator təsdiqi",
        "recover": "Admin şifrəsinin bərpası",
    }[purpose]
    form = form_type(request.POST or None)
    error = ""
    if request.method == "POST":
        # Wrong setup keys cannot probe validation details or trigger email.
        from django.conf import settings
        from django.utils.crypto import constant_time_compare

        with security.transaction.atomic():
            security.state_locked()
            allowed = security.throttle(
                "web-security:" + purpose + ":" + request.META.get("REMOTE_ADDR", ""),
                10,
                900,
            )
        if not allowed:
            error = security.ERROR
        elif purpose == "setup" and (
            len(settings.ADMIN_SETUP_SECRET) < 32
            or not constant_time_compare(
                request.POST.get("setup_secret", ""), settings.ADMIN_SETUP_SECRET
            )
        ):
            with security.transaction.atomic():
                security.state_locked()
                security.throttle(
                    "wrong-setup:" + request.META.get("REMOTE_ADDR", ""), 10, 900
                )
            error = security.ERROR
        elif form.is_valid():
            binding = secrets.token_urlsafe(32)
            result = security.issue(
                purpose,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password1"],
                setup_secret=form.cleaned_data.get("setup_secret", ""),
                owner_password=form.cleaned_data.get("owner_password", ""),
                actor=request.user if request.user.is_authenticated else None,
                binding=binding,
                source=request.META.get("REMOTE_ADDR", ""),
            )
            # Recovery always shows the same page and message for known/unknown accounts.
            if result.ok or purpose == "recover":
                request.session.cycle_key()
                request.session["admin_verification"] = {
                    "id": str(result.challenge.pk)
                    if result.ok
                    else str(secrets.token_hex(16)),
                    "binding": binding,
                }
                return redirect("owner_verify")
            error = result.error
    return render(
        request,
        "shop/owner_auth.html",
        {
            "heading": heading,
            "form": form,
            "error": error,
            "setup": purpose == "setup",
            "recovery": purpose == "recover",
            "administrators": ApprovedAdministrator.objects.select_related("user")
            if purpose == "invite"
            else [],
        },
    )


@protected_response
def setup(request):
    return operation(request, "setup")


@protected_response
def invite(request):
    return operation(request, "invite")


@protected_response
def recovery(request):
    return operation(request, "recover")


@protected_response
def verify(request):
    import uuid

    pending = request.session.get("admin_verification", {})
    try:
        challenge_id = uuid.UUID(pending.get("id", ""))
    except (ValueError, AttributeError):
        raise Http404
    form = VerificationForm(request.POST or None)
    error = ""
    if request.method == "POST":
        # Count every posted code, even malformed codes, against the same limit.
        if request.POST.get("approve") == "on":
            result = security.verify(
                challenge_id,
                request.POST.get("code", "")[:512],
                pending.get("binding", ""),
                actor=request.user,
            )
            if result.ok:
                request.session.pop("admin_verification", None)
                logout(request)
                messages.success(
                    request,
                    "Təsdiq tamamlandı. Admin istifadəçi adı və şifrənizlə daxil olun.",
                )
                return redirect("/admin/login/")
            error = security.ERROR
        else:
            error = "Əməliyyatı təsdiqləyin."
    return render(
        request,
        "shop/owner_auth.html",
        {
            "heading": "E-poçt təsdiqi",
            "form": form,
            "error": error,
            "verification": True,
        },
    )
