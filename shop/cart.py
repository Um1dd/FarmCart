from decimal import Decimal
from .models import Product


def variant_title(variant, lang):
    return (variant.name_ru if lang == "ru" else variant.name_az) if variant else ""


def availability(product, variant):
    limits = [
        n
        for n in (product.stock, variant.stock if variant else None, 99)
        if n is not None
    ]
    return min(limits)


def rows(request):
    cart = request.session.get("cart", {})
    lang = request.session.get("lang", "az")
    parsed = []
    for key, quantity in cart.items():
        try:
            parts = key.split(":")
            if len(parts) > 2:
                continue
            pid = int(parts[0])
            vid = int(parts[1]) if len(parts) == 2 else None
            quantity = min(99, max(1, int(quantity)))
            parsed.append((key, pid, vid, quantity))
        except (ValueError, TypeError):
            continue
    products = {
        p.pk: p
        for p in Product.objects.filter(
            pk__in=[x[1] for x in parsed], active=True
        ).prefetch_related("variants")
    }
    result = []
    remaining_stock = {pk: p.stock for pk, p in products.items()}
    for key, pid, vid, qty in parsed:
        product = products.get(pid)
        if not product:
            continue
        all_variants = list(product.variants.all())
        variants = [v for v in all_variants if v.active]
        variant = next((v for v in variants if v.pk == vid), None)
        if (vid and not variant) or (all_variants and not variant):
            continue
        qty = min(qty, availability(product, variant))
        if remaining_stock[pid] is not None:
            qty = min(qty, remaining_stock[pid])
            remaining_stock[pid] -= qty
        if qty < 1:
            continue
        price = variant.sale_price if variant else product.sale_price
        result.append(
            dict(
                key=key,
                product=product.localized(lang),
                variant=variant,
                variant_title=variant_title(variant, lang),
                quantity=qty,
                price=price,
                subtotal=price * qty,
            )
        )
    return result, sum((r["subtotal"] for r in result), Decimal("0"))
