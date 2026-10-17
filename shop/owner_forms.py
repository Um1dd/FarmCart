from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class AdminCredentialsForm(forms.Form):
    username = forms.CharField(
        label="Admin istifadəçi adı",
        max_length=150,
        initial="umid_w",
        validators=[User._meta.get_field("username").validators[0]],
    )
    password1 = forms.CharField(
        label="Yeni admin şifrəsi",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        max_length=256,
    )
    password2 = forms.CharField(
        label="Şifrəni təkrarlayın",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        max_length=256,
    )

    def clean(self):
        values = super().clean()
        if values.get("password1") != values.get("password2"):
            self.add_error("password2", "Şifrələr uyğun deyil.")
        if values.get("password1"):
            validate_password(
                values["password1"], User(username=values.get("username", ""))
            )
        return values


class SetupForm(AdminCredentialsForm):
    setup_secret = forms.CharField(
        label="Serverin ADMIN_SETUP_SECRET açarı",
        widget=forms.PasswordInput,
        max_length=512,
    )


class InviteForm(AdminCredentialsForm):
    owner_password = forms.CharField(
        label="Sahib hesabınızın cari şifrəsi",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        max_length=256,
    )
    username = forms.CharField(
        label="Əlavə admin istifadəçi adı",
        max_length=150,
        validators=[User._meta.get_field("username").validators[0]],
    )


class UnreflectedCodeInput(forms.TextInput):
    def format_value(self, value):
        return None


class VerificationForm(forms.Form):
    code = forms.RegexField(
        r"^\d{8}$",
        label="Gmail-ə göndərilən 8 rəqəmli kod",
        max_length=8,
        widget=UnreflectedCodeInput(
            attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}
        ),
    )
    approve = forms.BooleanField(label="Bu əməliyyatı təsdiq edirəm")


class OwnerAdminLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        from .owner_security import is_administrator

        super().confirm_login_allowed(user)
        if not is_administrator(user):
            raise ValidationError(
                self.error_messages["invalid_login"],
                code="invalid_login",
                params={"username": self.username_field.verbose_name},
            )
