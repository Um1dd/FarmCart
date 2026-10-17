from django import forms
from .i18n import translations


class DeliveryForm(forms.Form):
    customer_name = forms.CharField(max_length=100, required=False)
    delivery_phone = forms.RegexField(
        r"^\+?[0-9 ()-]{7,25}$", max_length=25, required=False
    )
    delivery_address = forms.CharField(
        max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2})
    )
    delivery_note = forms.CharField(
        max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, lang="az", **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.label = translations(lang)[name]
