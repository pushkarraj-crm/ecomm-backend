from django.test import TestCase

# Create your tests here.

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from .models import Product


class ProductSlugResponseTests(TestCase):
    def test_catalog_and_detail_expose_stored_slug(self):
        cache.clear()
        user = get_user_model().objects.create_user(
            email="slug-test@example.test", password="local-test-password"
        )
        product = Product.objects.create(
            seller=user,
            name="Test Desk Lamp",
            slug="stored-custom-lamp-slug",
            description="Test",
            status="approved",
        )
        client = APIClient()
        detail = client.get(f"/api/products/{product.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["slug"], "stored-custom-lamp-slug")
        catalog = client.get("/api/products/")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.data[0]["slug"], product.slug)
        cache.clear()
