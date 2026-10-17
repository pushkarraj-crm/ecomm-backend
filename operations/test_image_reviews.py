import io
from PIL import Image
from django.test import TestCase
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from products.models import Category, Product, ProductVariant, ProductImage


class ImageReviewTests(TestCase):
    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.admin = users.create_superuser("image-admin@example.test", "test-password")
        self.seller = users.create_user("image-seller@example.test", "test-password")
        self.seller.is_seller = True
        self.seller.seller_status = "approved"
        self.seller.save()
        self.client = APIClient()
        self.product = Product.objects.create(
            name="Review product",
            description="Test",
            seller=self.seller,
            category=Category.objects.create(name="Images"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, size="Free Size", color="Red", price=100, stock=1
        )
        self.image = ProductImage.objects.create(
            variant=self.variant, image="products/test.jpg", review_status="pending"
        )
        self.base = "/api/superadmin/resources/"

    def test_images_must_be_reviewed_before_product_approval(self):
        self.client.force_authenticate(self.admin)
        product_url = f"{self.base}products/{self.product.pk}/"
        image_url = f"{self.base}product-images/{self.image.pk}/"
        self.assertEqual(
            self.client.patch(
                product_url, {"status": "approved"}, format="json"
            ).status_code,
            400,
        )
        response = self.client.patch(
            image_url, {"review_status": "approved"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.client.patch(
                product_url, {"status": "approved"}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                image_url, {"review_status": "rejected"}, format="json"
            ).status_code,
            400,
        )
        response = self.client.patch(
            image_url,
            {"review_status": "rejected", "review_reason": "Visible watermark"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, "pending")
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.get(image_url).status_code, 403)

    def test_quality_checks_reject_bad_images_without_storing_files(self):
        self.client.force_authenticate(self.seller)

        def photo(size, blank=False):
            stream = io.BytesIO()
            image = (
                Image.new("RGB", size, "white")
                if blank
                else Image.effect_noise(size, 80).convert("RGB")
            )
            image.save(stream, format="PNG")
            return SimpleUploadedFile(
                "image.png", stream.getvalue(), content_type="image/png"
            )

        before = ProductImage.objects.count()
        response = self.client.post(
            "/api/seller/catalog/images/check/",
            {
                "images": [
                    photo((600, 600)),
                    photo((100, 100)),
                    photo((600, 600), True),
                    SimpleUploadedFile(
                        "invalid.png", b"broken", content_type="image/png"
                    ),
                ]
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [item["status"] for item in response.data["results"]],
            ["pending_review", "rejected", "rejected", "rejected"],
        )
        self.assertEqual(ProductImage.objects.count(), before)
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.post(
                "/api/seller/catalog/images/check/", {}, format="multipart"
            ).status_code,
            401,
        )
