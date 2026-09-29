from django.db import transaction

from .models import Product, ProductVariant, ProductImage, Review


# =========================
# PRODUCT SERVICE
# =========================
class ProductService:

    @staticmethod
    @transaction.atomic
    def create_product_with_variants(user, validated_data, images_by_variant):
        product = Product.objects.create(
            seller=user,
            name=validated_data['name'],
            description=validated_data['description'],
            category=validated_data['category'],
        )

        for index, variant_data in enumerate(validated_data['variants']):
            variant = ProductVariant.objects.create(
                product=product,
                **variant_data,
            )

            for image in images_by_variant[index]:
                ProductImage.objects.create(variant=variant, image=image)

        return product


# =========================
# REVIEW SERVICE
# =========================
class ReviewService:

    @staticmethod
    def add_review(user, product, rating, comment=''):
        return Review.objects.create(
            user=user,
            product=product,
            rating=rating,
            comment=comment,
        )
