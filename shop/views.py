from urllib.parse import urlencode
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q
from .models import Product, Region, Category, Video, StoreSettings, ProductVariant
from .cart import rows as cart_rows, availability
from .i18n import translations


def language(request):
    return request.session.get("lang", "az")


def tr(request):
    return translations(language(request))


def local(items, request):
    return [x.localized(language(request)) for x in items]


def home(request):
    return render(
        request,
        "shop/home.html",
        {
            "products": local(
                Product.objects.filter(active=True).select_related(
                    "region", "category"
                )[:8],
                request,
            ),
            "regions": local(Region.objects.all(), request),
            "videos": local(
                Video.objects.filter(active=True, placement="production")[:3], request
            ),
            "packing": local(
                Video.objects.filter(active=True, placement="packing")[:2], request
            ),
        },
    )


def catalog(request, region_id=None):
    qs = Product.objects.filter(active=True).select_related("region", "category")
    region = (
        get_object_or_404(Region, pk=region_id).localized(language(request))
        if region_id
        else None
    )
    if region:
        qs = qs.filter(region=region)
    q = request.GET.get("q", "")[:100]
    if q:
        qs = qs.filter(
            Q(name_az__icontains=q)
            | Q(name_ru__icontains=q)
            | Q(description_az__icontains=q)
            | Q(description_ru__icontains=q)
        )
    category = request.GET.get("category", "")
    if category.isdigit():
        qs = qs.filter(category_id=category)
    return render(
        request,
        "shop/catalog.html",
        {
            "products": local(qs, request),
            "region": region,
            "q": q,
            "categories": local(Category.objects.all(), request),
            "selected_category": category,
        },
    )


def detail(request, pk):
    p = get_object_or_404(Product, pk=pk, active=True).localized(language(request))
    p.region.localized(language(request))
    p.category.localized(language(request))
    return render(
        request,
        "shop/detail.html",
        {
            "product": p,
            "videos": local(p.video_set.filter(active=True), request),
            "variants": p.variants.filter(active=True),
            "requires_variant": p.variants.exists(),
        },
    )


@require_POST
def set_language(request):
    request.session["lang"] = "ru" if request.POST.get("lang") == "ru" else "az"
    return redirect(
        request.POST.get("next")
        if request.POST.get("next", "").startswith("/")
        and not request.POST.get("next", "").startswith("//")
        else "/"
    )


@require_POST
def cart_change(request, pk):
    product = get_object_or_404(Product, pk=pk, active=True)
    action = request.POST.get("action", "add")
    variant_id = request.POST.get("variant", "")
    variant = None
    if variant_id:
        if not variant_id.isdigit():
            return redirect("detail", pk=pk)
        variant = get_object_or_404(
            ProductVariant, pk=int(variant_id), product=product, active=True
        )
    key = str(pk) + (f":{variant.pk}" if variant else "")
    cart = request.session.get("cart", {}).copy()
    if action == "remove":
        cart.pop(key, None)
    else:
        if product.variants.exists() and not variant:
            messages.info(
                request,
                tr(request)[
                    "choose_variant"
                    if product.variants.filter(active=True).exists()
                    else "out_of_stock"
                ],
            )
            return redirect("detail", pk=pk)
        limit = availability(product, variant)
        if product.stock is not None:
            others = sum(
                r["quantity"]
                for r in cart_rows(request)[0]
                if r["product"].pk == pk and r["key"] != key
            )
            limit = min(limit, max(0, product.stock - others))
        if limit < 1:
            messages.error(request, tr(request)["out_of_stock"])
            return redirect("detail", pk=pk)
        try:
            qty = int(request.POST.get("quantity", "1"))
        except (ValueError, TypeError):
            qty = 1
        if action == "add":
            qty += int(cart.get(key, 0))
        cart[key] = min(limit, max(1, qty))
    request.session["cart"] = cart
    messages.success(request, tr(request)["added" if action == "add" else "changed"])
    target = request.POST.get("next", "/cart/")
    return redirect(
        target if target.startswith("/") and not target.startswith("//") else "/cart/"
    )


def cart(request):
    from .delivery_forms import DeliveryForm

    rows, total = cart_rows(request)
    t = tr(request)
    form = DeliveryForm(
        request.POST if request.method == "POST" else None,
        initial=request.session.get("delivery", {}),
        lang=language(request),
    )
    if request.method == "POST" and form.is_valid():
        request.session["delivery"] = form.cleaned_data
        messages.success(request, t["saved"])
        return redirect("cart")
    delivery = request.session.get("delivery", {})
    summary = (
        t["order_intro"]
        + "\n"
        + "\n".join(
            f"{r['product'].title} {r['variant_title'] or (r['product'].unit_ru if language(request) == 'ru' else r['product'].unit_az)} × {r['quantity']} ({r['price']} AZN): {r['subtotal']} AZN"
            for r in rows
        )
        + f"\n{t['total']}: {total} AZN"
    )
    for key in ["customer_name", "delivery_phone", "delivery_address", "delivery_note"]:
        if delivery.get(key):
            summary += "\n" + t[key] + ": " + delivery[key]
    settings = StoreSettings.objects.first()
    link = (
        "https://wa.me/"
        + settings.whatsapp.lstrip("+")
        + "?"
        + urlencode({"text": summary})
        if settings and settings.whatsapp and rows
        else ""
    )
    return render(
        request,
        "shop/cart.html",
        {
            "rows": rows,
            "total": total,
            "summary": summary,
            "whatsapp_link": link,
            "delivery_form": form,
        },
    )


def videos(request):
    return render(
        request,
        "shop/reels.html",
        {
            "videos": local(
                Video.objects.filter(active=True, reels=True).select_related("product"),
                request,
            )
        },
    )


def contact(request):
    return render(request, "shop/contact.html")


def auth(request, register=False):
    t = tr(request)
    error = ""
    form = UserCreationForm(request.POST or None) if register else None
    if request.method == "POST":
        # Bound login attempts per username and source; never trust forwarded headers.
        from .owner_security import (
            login_allowed,
            is_administrator,
            SecurityStateUnavailable,
        )
        from django.db import OperationalError

        try:
            allowed = login_allowed(
                request.META.get("REMOTE_ADDR", ""),
                request.POST.get("username", "")[:150],
            )
        except (OperationalError, SecurityStateUnavailable):
            allowed = False
        if not allowed:
            error = t["rate"]
        else:
            if register and form.is_valid():
                user = form.save()
                login(request, user)
                return redirect("account")
            elif not register:
                user = authenticate(
                    request,
                    username=request.POST.get("username"),
                    password=request.POST.get("password"),
                )
                if user and (not user.is_staff or is_administrator(user)):
                    login(request, user)
                    if user.is_staff:
                        request.session.set_expiry(1800)
                    return redirect("account")
            error = t["invalid"]
    return render(
        request, "shop/auth.html", {"register": register, "error": error, "form": form}
    )


@require_POST
def signout(request):
    logout(request)
    return redirect("home")


@login_required
def account(request):
    if request.method == "POST":
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        email = request.POST.get("email", "").strip()[:254]
        try:
            if email:
                validate_email(email)
        except ValidationError:
            messages.error(request, tr(request)["invalid"])
        else:
            u = request.user
            u.first_name = request.POST.get("first_name", "")[:150]
            u.last_name = request.POST.get("last_name", "")[:150]
            u.email = email if not u.is_staff else u.email
            u.save()
            messages.success(request, tr(request)["saved"])
    return render(request, "shop/account.html")
