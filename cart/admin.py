from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1


class CartAdmin(admin.ModelAdmin):
    exclude = ['user']
    list_display = ['id', 'user']
    inlines = [CartItemInline]

    def save_model(self, request, obj, form, change):
        if not obj.user:
            obj.user = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem)