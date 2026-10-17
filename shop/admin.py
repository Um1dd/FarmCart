from django.contrib import admin
from .models import Region, Category, Product, Video, StoreSettings
admin.site.site_header = 'FarmCart · Store management'
admin.site.site_title = 'FarmCart administration'
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name_az','region','category','price','discount','active','sample']
    list_filter = ['region','category','active','sample']
    search_fields = ['name_az','name_ru']
@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['name_az','product','placement','reels','active','position']
    list_filter = ['placement','reels','active']
admin.site.register(Region)
admin.site.register(Category)
@admin.register(StoreSettings)
class SettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return not StoreSettings.objects.exists()
    def has_delete_permission(self, request, obj=None): return False

from django.utils.html import format_html

def picture_preview(obj):
    if obj and obj.picture:
        return format_html('<div style="position:relative;width:160px;height:130px;overflow:hidden;border-radius:4px"><img src="{}" style="width:100%;height:100%;object-fit:cover;{}" alt=""></div>',obj.picture,obj.art_style)
    return '—'
picture_preview.short_description='Image preview'
ProductAdmin.readonly_fields=[picture_preview]
# Region editing uses the same live preview as the catalog.
admin.site.unregister(Region)
@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    readonly_fields=[picture_preview]

def video_preview(obj):
    if obj and obj.file:
        return format_html('<video src="{}" controls preload="metadata" style="max-width:360px;max-height:420px"></video>',obj.file.url)
    return '—'
video_preview.short_description='Video preview'
VideoAdmin.readonly_fields=[video_preview]
