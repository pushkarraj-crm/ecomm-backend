from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers
from accounts.models import User
from customers.models import SupportTicket
from products.models import Product, Category, StoreBanner, DeliveryArea, ProductVariant
from products.serializers import ProductReadSerializer
from orders.models import Coupon, CustomerOrderRequest


class ValidatedModelSerializer(serializers.ModelSerializer):
    def validate_image(self, value):
        if value and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Images must be smaller than 2 MB.")
        return value

    def validate(self, attrs):
        instance = self.instance.__class__.objects.get(pk=self.instance.pk) if self.instance else self.Meta.model()
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.full_clean(exclude=[field.name for field in instance._meta.fields if field.name not in self.fields])
        except ModelValidationError as error:
            raise serializers.ValidationError(error.message_dict if hasattr(error, 'message_dict') else error.messages)
        return attrs


class UserRead(serializers.ModelSerializer):
    store_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    def get_store_name(self, obj):
        profile = getattr(obj, 'seller_profile', None)
        return (profile.store_name or profile.business_name) if profile else ''

    def get_name(self, obj):
        profile = getattr(obj, 'customer_profile', None)
        return profile.name if profile else ''

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'store_name', 'is_seller', 'seller_status', 'is_blacklisted', 'is_active', 'last_login']


class SellerWrite(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['seller_status', 'is_blacklisted']


class CustomerWrite(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['is_active']


class ProductRead(ProductReadSerializer):
    class Meta(ProductReadSerializer.Meta):
        fields = ProductReadSerializer.Meta.fields + ['status', 'is_active', 'created_at']


class ProductWrite(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['status', 'is_active']


class CategoryWrite(ValidatedModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'parent', 'image']
        read_only_fields = ['id']

    def validate_parent(self, value):
        seen = {self.instance.pk} if self.instance else set()
        current = value
        while current:
            if current.pk in seen:
                raise serializers.ValidationError('Category hierarchy cannot contain a cycle.')
            seen.add(current.pk)
            current = current.parent
        return value


class BannerWrite(ValidatedModelSerializer):
    class Meta:
        model = StoreBanner
        fields = ['id', 'title', 'subtitle', 'image', 'category', 'is_active', 'position']
        read_only_fields = ['id']


class DeliveryWrite(ValidatedModelSerializer):
    class Meta:
        model = DeliveryArea
        fields = ['id', 'postal_code', 'city', 'min_days', 'max_days', 'is_active']
        read_only_fields = ['id']


class CouponWrite(ValidatedModelSerializer):
    class Meta:
        model = Coupon
        fields = ['id', 'code', 'seller', 'percent', 'minimum_subtotal', 'starts_at', 'expires_at', 'is_active']
        read_only_fields = ['id']

    def validate_code(self, value):
        return value.strip().upper()

    def validate_seller(self, value):
        if not value.is_seller or value.is_superuser:
            raise serializers.ValidationError('Choose a seller account.')
        return value


class RequestWrite(serializers.ModelSerializer):
    class Meta:
        model = CustomerOrderRequest
        fields = ['status', 'response']


class SupportWrite(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ['status', 'response']


class InventoryWrite(ValidatedModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ['price', 'original_price', 'stock']
