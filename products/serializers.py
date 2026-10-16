from rest_framework import serializers
from decimal import Decimal
from .models import Category, Product, ProductVariant, ProductImage, Review


# =========================
# 🖼️ PRODUCT IMAGE SERIALIZER
# =========================
class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image']


# =========================
# 🔥 VARIANT (READ)
# =========================
class ProductVariantReadSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = ProductVariant
        fields = ['id', 'size', 'color', 'price', 'stock', 'images']


# =========================
# 🛍️ PRODUCT (READ)
# =========================
class ProductReadSerializer(serializers.ModelSerializer):
    variants = ProductVariantReadSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    seller = serializers.SerializerMethodField()
    price = serializers.FloatField(source='catalog_price', read_only=True, allow_null=True)
    average_rating = serializers.FloatField(source='catalog_rating', read_only=True, allow_null=True)
    review_count = serializers.IntegerField(source='catalog_review_count', read_only=True)
    in_stock = serializers.BooleanField(source='catalog_in_stock', read_only=True)

    def get_seller(self, instance):
        profile = getattr(instance.seller, 'seller_profile', None)
        return {'id': instance.seller_id, 'store_name': (profile.store_name or profile.business_name) if profile else 'Marketplace seller'}

    class Meta:
        model = Product
        fields = [
            'id', 'slug', 'name', 'description', 'category', 'return_policy',
            'return_days', 'variants', 'category_name', 'seller', 'price',
            'average_rating', 'review_count', 'in_stock',
        ]


# =========================
# ✍️ VARIANT (WRITE)
# =========================
class ProductVariantWriteSerializer(serializers.Serializer):
    size = serializers.CharField()
    color = serializers.CharField()
    price = serializers.FloatField()
    stock = serializers.IntegerField()

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be > 0")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative")
        return value


# =========================
# ✍️ PRODUCT (WRITE)
# =========================
class ProductWriteSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField()
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    variants = ProductVariantWriteSerializer(many=True)
    return_policy = serializers.ChoiceField(
        choices=Product.RETURN_POLICY_CHOICES,
        default='no_return',
    )
    return_days = serializers.ChoiceField(
        choices=Product.RETURN_DAY_CHOICES,
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        return_policy = attrs.get('return_policy', 'no_return')
        return_days = attrs.get('return_days')
        if return_policy == 'no_return' and return_days is not None:
            raise serializers.ValidationError({
                'return_days': 'Leave return_days empty when policy is no_return.'
            })
        if return_policy == 'return_and_exchange' and return_days is None:
            raise serializers.ValidationError({
                'return_days': 'Choose 2, 5, or 7 days for return and exchange.'
            })
        attrs['return_days'] = return_days
        return attrs


class ReviewWriteSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(
        source='product',
        queryset=Product.objects.all(),
    )
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, default='')


# =========================
# ⭐ REVIEW SERIALIZER
# =========================
class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['id', 'product', 'rating', 'comment']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value


class ProductImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()

    def validate_image(self, value):
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Image too large (max 2MB)")
        return value


class CatalogFilterSerializer(serializers.Serializer):
    category = serializers.IntegerField(min_value=1, required=False)
    seller = serializers.IntegerField(min_value=1, required=False)
    min_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'), required=False)
    max_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'), required=False)
    size = serializers.CharField(max_length=50, required=False)
    color = serializers.CharField(max_length=50, required=False)
    in_stock = serializers.BooleanField(required=False)
    min_rating = serializers.DecimalField(max_digits=2, decimal_places=1, min_value=Decimal('0'), max_value=Decimal('5'), required=False)

    def validate(self, attrs):
        if attrs.get('min_price', 0) > attrs.get('max_price', Decimal('Infinity')):
            raise serializers.ValidationError({'max_price': 'Must be at least min_price.'})
        return attrs
