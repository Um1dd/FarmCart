from django.contrib import admin
from django.urls import path, include
from shop.media import catalog_media
from shop import owner_views

urlpatterns = [
    path("admin/verify/", owner_views.verify, name="owner_verify"),
    path("media/<path:path>", catalog_media),
    path("admin/", admin.site.urls),
    path("", include("shop.urls")),
]
