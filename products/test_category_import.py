import io, json
from django.core.management import call_command
from django.test import TestCase
from .models import Category, Product
from .management.commands.seed_marketplace_categories import DATA_FILE
from django.contrib.auth import get_user_model


class MarketplaceCategoryImportTests(TestCase):
    def test_import_is_idempotent_and_preserves_existing_products_and_hierarchy(self):
        women = Category.objects.create(name="Women Wear")
        custom = Category.objects.create(name="Existing custom category", parent=women)
        owner = get_user_model().objects.create_user(
            email="category-owner@example.test", password="test-password"
        )
        product = Product.objects.create(
            seller=owner,
            category=custom,
            name="Existing product",
            description="Keep assignment",
        )
        call_command("seed_marketplace_categories", stdout=io.StringIO())
        count = Category.objects.count()
        call_command("seed_marketplace_categories", stdout=io.StringIO())
        self.assertEqual(Category.objects.count(), count)
        product.refresh_from_db()
        self.assertEqual(product.category_id, custom.pk)
        self.assertTrue(Category.objects.filter(pk=women.pk, parent=None).exists())
        roots = json.loads(DATA_FILE.read_text())["categories"]
        self.assertEqual(len(roots), 13)

        def check(nodes, parent=None):
            for node in nodes:
                category = Category.objects.get(parent=parent, name=node["name"])
                check(node.get("children", []), category)

        check(roots)
        response = self.client.get("/api/products/categories/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(row["name"] == "Sports" for row in response.json()))
