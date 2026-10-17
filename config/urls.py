from django.contrib import admin
from django.urls import path, include
from shop.media import catalog_media
urlpatterns = [path('media/<path:path>', catalog_media), path('admin/', admin.site.urls), path('', include('shop.urls'))]

