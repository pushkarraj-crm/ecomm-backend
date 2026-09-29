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
        fields = ['id', 'name', 'description', 'category', 'variants']


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
