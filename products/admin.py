from django.contrib import admin
from .models import Product, ProductVariant, ProductImage, Review, Category
from accounts.models import User


# =========================
# IMAGE INLINE (inside variant)
# =========================
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


# =========================
# VARIANT INLINE (inside product)
# =========================
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


# =========================
# PRODUCT ADMIN
# =========================
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'seller', 'status', 'created_at']
    inlines = [ProductVariantInline]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "seller":
            kwargs["queryset"] = User.objects.filter(is_seller=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not obj.seller:
            obj.seller = request.user
        super().save_model(request, obj, form, change)


# =========================
# VARIANT ADMIN
# =========================
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'size', 'color', 'price', 'stock']
    inlines = [ProductImageInline]


# =========================
# CATEGORY ADMIN
# =========================
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'parent']
    list_filter = ['parent']
    search_fields = ['name']


# =========================
# REGISTER
# =========================
admin.site.register(Product, ProductAdmin)
admin.site.register(ProductVariant, ProductVariantAdmin)
admin.site.register(ProductImage)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Review)

from .models import StoreBanner, DeliveryArea

@admin.register(StoreBanner)
class StoreBannerAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'is_active', 'position']
    list_editable = ['is_active', 'position']

@admin.register(DeliveryArea)
class DeliveryAreaAdmin(admin.ModelAdmin):
    list_display = ['postal_code', 'city', 'min_days', 'max_days', 'is_active']
    search_fields = ['postal_code', 'city']
