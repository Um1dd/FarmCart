from django import forms
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from cloudinary.exceptions import Error as CloudinaryError
from requests.exceptions import RequestException


class DurableUploadForm(forms.ModelForm):
    def clean(self):
        data = super().clean()
        if self.files and not settings.MEDIA_DURABLE:
            raise forms.ValidationError(
                "Qalıcı şəkil/video yaddaşı konfiqurasiya edilməyib. Serverdə Cloudinary məlumatlarını əlavə edin; fayllar müvəqqəti diskə yüklənməyəcək."
            )
        return data


class UploadAdminMixin:
    form = DurableUploadForm

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except (CloudinaryError, RequestException, OSError):
            messages.error(
                request,
                "Fayl yaddaşa yüklənmədi. Yaddaş bağlantısını yoxlayın və faylı yenidən seçin.",
            )
            return redirect(request.path)
