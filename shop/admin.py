from django.contrib import admin
from .models import Region, Category, Product, Video, StoreSettings, ProductVariant
from .admin_forms import UploadAdminMixin

admin.site.site_header = "FarmCart · Store management"
admin.site.site_title = "FarmCart administration"


@admin.register(Product)
class ProductAdmin(UploadAdminMixin, admin.ModelAdmin):
    list_display = [
        "name_az",
        "region",
        "category",
        "price",
        "discount",
        "stock",
        "active",
        "sample",
    ]
    list_filter = ["region", "category", "active", "sample"]
    search_fields = ["name_az", "name_ru"]


@admin.register(Video)
class VideoAdmin(UploadAdminMixin, admin.ModelAdmin):
    list_display = ["name_az", "product", "placement", "reels", "active", "position"]
    list_filter = ["placement", "reels", "active"]


admin.site.register(Region)
admin.site.register(Category)


@admin.register(StoreSettings)
class SettingsAdmin(UploadAdminMixin, admin.ModelAdmin):
    def has_add_permission(self, request):
        return (
            super().has_add_permission(request) and not StoreSettings.objects.exists()
        )

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)


from django.utils.html import format_html


def picture_preview(obj):
    if obj and obj.picture:
        return format_html(
            '<div style="position:relative;width:160px;height:130px;overflow:hidden;border-radius:4px"><img src="{}" style="width:100%;height:100%;object-fit:cover;{}" alt=""></div>',
            obj.picture,
            obj.art_style,
        )
    return "—"


picture_preview.short_description = "Image preview"
ProductAdmin.readonly_fields = [picture_preview]
# Region editing uses the same live preview as the catalog.
admin.site.unregister(Region)


@admin.register(Region)
class RegionAdmin(UploadAdminMixin, admin.ModelAdmin):
    readonly_fields = [picture_preview]


def video_preview(obj):
    if obj and obj.file:
        return format_html(
            '<video src="{}" controls preload="metadata" style="max-width:360px;max-height:420px"></video>',
            obj.file.url,
        )
    return "—"


video_preview.short_description = "Video preview"
VideoAdmin.readonly_fields = [video_preview]

# Role changes and account creation must use the owner-approval workflow.
from django.contrib.auth.models import User, Group

for auth_model in (User, Group):
    if admin.site.is_registered(auth_model):
        admin.site.unregister(auth_model)


@admin.register(User)
class CustomerDirectoryAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_staff=False, is_superuser=False)

    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "date_joined",
        "is_active",
    ]
    search_fields = ["username", "email", "first_name", "last_name"]
    fields = [
        "username",
        "email",
        "first_name",
        "last_name",
        "date_joined",
        "is_active",
    ]
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        from .owner_security import is_administrator

        return is_administrator(request.user)

    def get_model_perms(self, request):
        return {"view": self.has_view_permission(request)}


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


ProductAdmin.inlines = [ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ["name_az", "name_ru", "product", "price", "stock", "active"]
    list_filter = ["active", "product__region"]
    search_fields = ["name_az", "name_ru", "product__name_az", "product__name_ru"]
    list_select_related = ["product"]
