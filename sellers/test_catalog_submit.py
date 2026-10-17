import io, tempfile, uuid, json
from unittest.mock import patch
from PIL import Image
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from products.models import Category, Product, ProductImage
from products.services import ProductService
from .models import SellerCatalogSubmission


class CatalogSubmissionTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.settings = override_settings(MEDIA_ROOT=self.media.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.addCleanup(self.media.cleanup)
        self.seller = get_user_model().objects.create_user(
            email="wizard@example.test",
            password="test-password",
        )
        self.seller.is_seller = True
        self.seller.seller_status = "approved"
        self.seller.save()
        self.category = Category.objects.create(name="Pillows")
        self.client = APIClient()
        self.client.force_authenticate(self.seller)
        self.url = "/api/seller/catalog/submit/"
        self.submission_id = str(uuid.uuid4())

    def photo(self):
        stream = io.BytesIO()
        Image.effect_noise((600, 600), 80).convert("RGB").save(stream, format="PNG")
        return SimpleUploadedFile(
            "product.png", stream.getvalue(), content_type="image/png"
        )

    def product(self, name="Test pillow"):
        return {
            "name": name,
            "description": "Cotton pillow",
            "category": self.category.pk,
            "variants": [
                {"size": "Free Size", "color": "Red", "price": 100, "stock": 4}
            ],
            "catalog_details": {
                "gst_rate": "5",
                "hsn_code": "9404",
                "net_weight_g": "500",
                "net_quantity": 1,
                "material": "Cotton",
                "manufacturer_name": "Demo Manufacturing",
                "manufacturer_address": "Demo business address",
                "length": "20",
                "dimension_unit": "cm",
            },
        }

    def submit(self, products, submission_id=None):
        body = {
            "submission_id": submission_id or self.submission_id,
            "products": json.dumps(products),
        }
        for index in range(len(products)):
            body[f"product_{index}_images"] = self.photo()
        return self.client.post(self.url, body, format="multipart")

    def test_multi_product_catalog_persists_details_images_and_pending_approval(self):
        response = self.submit([self.product(), self.product("Second pillow")])
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(ProductImage.objects.count(), 2)
        for product in Product.objects.all():
            self.assertEqual(product.seller_id, self.seller.pk)
            self.assertEqual(product.status, "pending")
            self.assertEqual(product.catalog_details["gst_rate"], "5.00")
            detail = self.client.get(f"/api/seller/catalog/{product.pk}/")
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(
                detail.data["catalog_details"]["manufacturer_name"],
                "Demo Manufacturing",
            )
        retry = self.submit([self.product(), self.product("Second pillow")])
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(retry.data["product_ids"], response.data["product_ids"])

    def test_invalid_product_or_attributes_do_not_create_partial_catalog(self):
        invalid = self.product()
        invalid["catalog_details"]["gst_rate"] = "101"
        response = self.submit([self.product(), invalid])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(SellerCatalogSubmission.objects.count(), 0)
        invalid = self.product()
        invalid["catalog_details"]["unknown_secret"] = "no"
        self.assertEqual(self.submit([invalid]).status_code, 400)
        parent = Category.objects.create(name="Parent")
        self.category.parent = parent
        self.category.save()
        invalid = self.product()
        invalid["category"] = parent.pk
        self.assertEqual(self.submit([invalid]).status_code, 400)
        invalid = self.product()
        invalid["seller"] = 999
        self.assertEqual(self.submit([invalid]).status_code, 400)

    def test_images_and_approved_seller_are_required(self):
        response = self.client.post(
            self.url,
            {
                "submission_id": self.submission_id,
                "products": json.dumps([self.product()]),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.seller.seller_status = "pending"
        self.seller.save()
        self.assertEqual(self.submit([self.product()]).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.submit([self.product()]).status_code, 401)

    def test_database_and_uploaded_files_roll_back_if_a_later_product_fails(self):
        original = ProductService.create_product_with_variants
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("Simulated failure")
            return original(*args, **kwargs)

        with patch(
            "sellers.catalog_submit.ProductService.create_product_with_variants",
            side_effect=fail_second,
        ):
            with self.assertRaises(RuntimeError):
                self.submit([self.product(), self.product("Second")])
        self.assertFalse(Product.objects.exists())
        self.assertFalse(SellerCatalogSubmission.objects.exists())
        from pathlib import Path

        self.assertFalse(
            any(path.is_file() for path in Path(self.media.name).rglob("*"))
        )
