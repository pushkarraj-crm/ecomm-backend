from rest_framework import serializers
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

    class Meta:
        model = Product
        fields = [
            'id', 'slug', 'name', 'description', 'category', 'return_policy',
            'return_days', 'variants',
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
