from .models import Region, StoreSettings
from .cart import rows
from .i18n import translations


def store(request):
    lang = request.session.get("lang", "az")
    return {
        "lang": lang,
        "t": translations(lang),
        "store": StoreSettings.objects.first(),
        "nav_regions": [r.localized(lang) for r in Region.objects.all()],
        "cart_count": sum(r["quantity"] for r in rows(request)[0]),
    }
