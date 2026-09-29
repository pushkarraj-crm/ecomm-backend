from django.contrib import admin
from .models import Order, Refund, SellerOrder, OrderItem
from .services import update_refund_status


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class SellerOrderInline(admin.TabularInline):
    model = SellerOrder
    extra = 0


class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'total_amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    inlines = [SellerOrderInline]


class SellerOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'seller', 'total_amount', 'status']
    inlines = [OrderItemInline]


admin.site.register(Order, OrderAdmin)
admin.site.register(SellerOrder, SellerOrderAdmin)
admin.site.register(OrderItem)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['id', 'seller_order', 'amount_paise', 'status', 'razorpay_refund_id', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['seller_order__seller__email', 'seller_order__order__id', 'razorpay_refund_id']
    readonly_fields = ['payment', 'requested_by', 'idempotency_key', 'amount_paise', 'razorpay_refund_id']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        update_refund_status(obj.id, obj.status, obj.failure_reason)
