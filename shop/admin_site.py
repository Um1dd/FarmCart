from django.contrib.admin.apps import AdminConfig
from django.contrib.admin.sites import AdminSite
from django.urls import path
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.decorators import method_decorator


class OwnerAdminConfig(AdminConfig):
    default_site = "shop.admin_site.OwnerAdminSite"


class OwnerAdminSite(AdminSite):
    site_header = "FarmCart · Store management"
    site_title = "FarmCart administration"
    login_template = "admin/owner_login.html"
    index_template = "admin/owner_index.html"

    @property
    def login_form(self):
        from .owner_forms import OwnerAdminLoginForm

        return OwnerAdminLoginForm

    def has_permission(self, request):
        from .owner_security import is_administrator

        return is_administrator(request.user)

    def each_context(self, request):
        context = super().each_context(request)
        from .owner_security import is_owner

        context["verified_owner"] = is_owner(request.user)
        return context

    def get_urls(self):
        from . import owner_views

        return [
            path("setup/", owner_views.setup, name="owner_setup"),
            path("verify/", owner_views.verify, name="owner_verify"),
            path("owner/administrators/", owner_views.invite, name="owner_invite"),
            path("recover/", owner_views.recovery, name="owner_recover"),
        ] + super().get_urls()

    @method_decorator(sensitive_post_parameters())
    def login(self, request, extra_context=None):
        if request.method == "POST":
            from .owner_security import login_allowed, SecurityStateUnavailable
            from django.db import OperationalError

            try:
                allowed = login_allowed(
                    request.META.get("REMOTE_ADDR", ""),
                    request.POST.get("username", "")[:150],
                )
            except (OperationalError, SecurityStateUnavailable):
                from django.http import HttpResponse

                return HttpResponse(
                    "Admin təhlükəsizliyi müvəqqəti əlçatan deyil.", status=503
                )
            if not allowed:
                from django.http import HttpResponse

                return HttpResponse(
                    "Çox sayda cəhd. 15 dəqiqə sonra yenidən yoxlayın.", status=429
                )
        response = super().login(request, extra_context)
        if (
            request.method == "POST"
            and response.status_code == 302
            and self.has_permission(request)
        ):
            request.session.set_expiry(1800)
        return response
