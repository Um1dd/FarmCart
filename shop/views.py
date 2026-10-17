from decimal import Decimal
from urllib.parse import urlencode
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Q
from .models import Product, Region, Category, Video, StoreSettings
from .i18n import translations

def language(request): return request.session.get('lang','az')
def tr(request): return translations(language(request))
def local(items, request): return [x.localized(language(request)) for x in items]
def home(request):
    return render(request,'shop/home.html',{'products':local(Product.objects.filter(active=True).select_related('region','category')[:8],request),'regions':local(Region.objects.all(),request),'videos':local(Video.objects.filter(active=True,placement='production')[:3],request),'packing':local(Video.objects.filter(active=True,placement='packing')[:2],request)})
def catalog(request, region_id=None):
    qs = Product.objects.filter(active=True).select_related('region','category')
    region = get_object_or_404(Region,pk=region_id).localized(language(request)) if region_id else None
    if region: qs = qs.filter(region=region)
    q = request.GET.get('q','')[:100]
    if q: qs = qs.filter(Q(name_az__icontains=q)|Q(name_ru__icontains=q)|Q(description_az__icontains=q)|Q(description_ru__icontains=q))
    category = request.GET.get('category','')
    if category.isdigit(): qs = qs.filter(category_id=category)
    return render(request,'shop/catalog.html',{'products':local(qs,request),'region':region,'q':q,'categories':local(Category.objects.all(),request),'selected_category':category})
def detail(request, pk):
    p = get_object_or_404(Product,pk=pk,active=True).localized(language(request))
    p.region.localized(language(request)); p.category.localized(language(request))
    return render(request,'shop/detail.html',{'product':p,'videos':local(p.video_set.filter(active=True),request)})
@require_POST
def set_language(request):
    request.session['lang'] = 'ru' if request.POST.get('lang') == 'ru' else 'az'
    return redirect(request.POST.get('next') if request.POST.get('next','').startswith('/') and not request.POST.get('next','').startswith('//') else '/')
def cart_rows(request):
    cart = request.session.get('cart',{})
    rows=[]
    for p in Product.objects.filter(pk__in=cart.keys(),active=True):
        qty=min(99,max(1,int(cart[str(p.pk)])))
        rows.append({'product':p.localized(language(request)),'quantity':qty,'subtotal':p.sale_price*qty})
    return rows, sum((r['subtotal'] for r in rows),Decimal('0'))
@require_POST
def cart_change(request, pk):
    p = get_object_or_404(Product,pk=pk,active=True)
    cart = request.session.get('cart',{}).copy()
    action=request.POST.get('action','add')
    if action=='remove': cart.pop(str(pk),None)
    else:
        try: qty=int(request.POST.get('quantity','1'))
        except ValueError: qty=1
        if action=='add': qty+=int(cart.get(str(pk),0))
        cart[str(pk)]=min(99,max(1,qty))
    request.session['cart']=cart
    messages.success(request,tr(request)['added' if action=='add' else 'changed'])
    target=request.POST.get('next','/cart/')
    return redirect(target if target.startswith('/') and not target.startswith('//') else '/cart/')
def cart(request):
    rows,total=cart_rows(request); t=tr(request)
    summary=t['order_intro']+'\n'+'\n'.join(f"{r['product'].title} × {r['quantity']} ({r['product'].sale_price} AZN): {r['subtotal']} AZN" for r in rows)+f"\n{t['total']}: {total} AZN"
    settings=StoreSettings.objects.first()
    link='https://wa.me/'+settings.whatsapp.lstrip('+')+'?'+urlencode({'text':summary}) if settings and settings.whatsapp and rows else ''
    return render(request,'shop/cart.html',{'rows':rows,'total':total,'summary':summary,'whatsapp_link':link})
def videos(request): return render(request,'shop/reels.html',{'videos':local(Video.objects.filter(active=True,reels=True).select_related('product'),request)})
def contact(request): return render(request,'shop/contact.html')
def auth(request, register=False):
    t=tr(request); error=''; form=UserCreationForm(request.POST or None) if register else None
    if request.method=='POST':
        # Bound login attempts per username and source; never trust forwarded headers.
        key='auth:'+request.META.get('REMOTE_ADDR','')+':'+request.POST.get('username','')[:150].lower()
        attempts=cache.get(key,0)
        if attempts>=10: error=t['rate']
        else:
            cache.set(key,attempts+1,300)
            if register and form.is_valid():
                user=form.save(); login(request,user); cache.delete(key); return redirect('account')
            elif not register:
                user=authenticate(request,username=request.POST.get('username'),password=request.POST.get('password'))
                if user: login(request,user); cache.delete(key); return redirect('account')
            error=t['invalid']
    return render(request,'shop/auth.html',{'register':register,'error':error,'form':form})
@require_POST
def signout(request): logout(request); return redirect('home')
@login_required
def account(request):
    if request.method=='POST':
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        email=request.POST.get('email','').strip()[:254]
        try:
            if email: validate_email(email)
        except ValidationError: messages.error(request,tr(request)['invalid'])
        else:
            u=request.user; u.first_name=request.POST.get('first_name','')[:150]; u.last_name=request.POST.get('last_name','')[:150]; u.email=email; u.save(); messages.success(request,tr(request)['saved'])
    return render(request,'shop/account.html')
