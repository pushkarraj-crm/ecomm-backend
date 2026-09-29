from django.contrib import admin
from .models import BankAccount, KYC, Payout, SellerProfile


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ['id', 'seller', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['seller__business_name', 'seller__user__email']
    list_editable = ['status']
    readonly_fields = ['seller', 'amount', 'created_at']


admin.site.register(SellerProfile)
admin.site.register(KYC)
admin.site.register(BankAccount)
