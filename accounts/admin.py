from django.contrib import admin
from .models import User


class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'is_seller', 'seller_status', 'is_blacklisted']
    list_filter = ['is_seller', 'seller_status', 'is_blacklisted']
    search_fields = ['email']


admin.site.register(User, UserAdmin)