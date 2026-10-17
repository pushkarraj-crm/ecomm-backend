from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from products.models import Category, Product, ProductVariant, Review
from sellers.models import SellerProfile


class MarketplaceCatalogTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.seller = get_user_model().objects.create_user(
            "seller@example.test", "password"
        )
        self.seller.is_seller = True
        self.seller.seller_status = "approved"
        self.seller.save()
        SellerProfile.objects.create(
            user=self.seller,
            business_name="Demo Shop",
            store_name="Public Shop",
            gst_number="PRIVATE",
        )
        self.parent = Category.objects.create(name="Clothing")
        self.child = Category.objects.create(name="Shirts", parent=self.parent)
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.child,
            name="Cotton shirt",
            description="Cotton",
            status="approved",
        )
        self.blue = ProductVariant.objects.create(
            product=self.product, size="M", color="Blue", price=200, stock=4
        )
        ProductVariant.objects.create(
            product=self.product, size="L", color="Red", price=500, stock=3
        )
        self.other = Product.objects.create(
            seller=self.seller, name="Sold out", description="Test", status="approved"
        )
        ProductVariant.objects.create(
            product=self.other, size="S", color="Red", price=100, stock=0
        )
        Review.objects.create(product=self.product, user=self.seller, rating=4)
        Review.objects.create(product=self.product, user=self.seller, rating=5)
        cache.clear()

    def results(self, **query):
        response = self.client.get("/api/products/", query)
        self.assertEqual(response.status_code, 200, response.data)
        return (
            response.data["results"]
            if isinstance(response.data, dict)
            else response.data
        )

    def test_category_includes_descendants_and_preserves_legacy_response(self):
        self.assertIsInstance(self.client.get("/api/products/").data, list)
        self.assertEqual(
            [p["id"] for p in self.results(category=self.parent.pk)], [self.product.pk]
        )

    def test_multiple_category_branches_include_descendants_without_duplicates(self):
        second = Category.objects.create(name="Home")
        self.other.category = second
        self.other.save()
        cache.clear()
        result = self.results(category_ids=f"{self.parent.pk},{second.pk}")
        self.assertEqual(
            {row["id"] for row in result}, {self.product.pk, self.other.pk}
        )
        result = self.results(category_ids=f"{self.parent.pk},{self.child.pk}")
        self.assertEqual([row["id"] for row in result], [self.product.pk])
        result = self.results(
            category_ids=str(self.child.pk), color="Blue", max_price=250
        )
        self.assertEqual([row["id"] for row in result], [self.product.pk])
        for value in ["", "abc", "0", "1,-2", ",1", ",".join(["1"] * 1001)]:
            self.assertEqual(
                self.client.get("/api/products/", {"category_ids": value}).status_code,
                400,
            )

    def test_variant_constraints_match_one_stocked_variant(self):
        self.assertEqual(self.results(size="M", color="Red"), [])
        self.assertEqual(self.results(color="Red", max_price="250"), [])
        self.assertEqual(
            [p["id"] for p in self.results(size="m", color="blue", max_price="250")],
            [self.product.pk],
        )

    def test_stock_rating_and_seller_filters(self):
        self.assertEqual(
            [p["id"] for p in self.results(in_stock="false")], [self.other.pk]
        )
        self.assertEqual(
            [p["id"] for p in self.results(min_rating="4.5", seller=self.seller.pk)],
            [self.product.pk],
        )
        self.assertEqual(self.results(min_rating="5"), [])

    def test_summaries_do_not_expose_seller_private_data(self):
        data = self.client.get(f"/api/products/{self.product.pk}/").data
        self.assertEqual(
            data["seller"], {"id": self.seller.pk, "store_name": "Public Shop"}
        )
        self.assertEqual(data["price"], 200)
        self.assertEqual(data["average_rating"], 4.5)
        self.assertEqual(data["review_count"], 2)
        self.assertTrue(data["in_stock"])
        self.assertNotIn("PRIVATE", str(data))
        self.assertNotIn(self.seller.email, str(data))

    def test_invalid_filters_return_400(self):
        for query in [
            {"min_price": "-1"},
            {"min_price": "500", "max_price": "100"},
            {"category": "abc"},
            {"min_rating": "6"},
            {"in_stock": "maybe"},
            {"max_price": "NaN"},
        ]:
            with self.subTest(query=query):
                self.assertEqual(
                    self.client.get("/api/products/", query).status_code, 400
                )

    def test_pending_and_inactive_products_are_not_public(self):
        self.product.status = "pending"
        with self.captureOnCommitCallbacks(execute=True):
            self.product.save()
        self.assertEqual(
            self.client.get(f"/api/products/{self.product.pk}/").status_code, 404
        )
        self.assertNotIn(self.product.pk, [p["id"] for p in self.results()])
        self.product.status = "approved"
        self.product.is_active = False
        with self.captureOnCommitCallbacks(execute=True):
            self.product.save()
        self.assertEqual(
            self.client.get(f"/api/products/{self.product.pk}/").status_code, 404
        )

    def test_stock_and_review_changes_invalidate_public_cache(self):
        url = f"/api/products/{self.product.pk}/"
        self.assertEqual(self.client.get(url).data["price"], 200)
        self.blue.price = 250
        with self.captureOnCommitCallbacks(execute=True):
            self.blue.save()
        self.assertEqual(self.client.get(url).data["price"], 250)
        with self.captureOnCommitCallbacks(execute=True):
            Review.objects.create(product=self.product, user=self.seller, rating=3)
        self.assertEqual(self.client.get(url).data["review_count"], 3)

    def test_filter_order_and_pagination(self):
        response = self.client.get(
            "/api/products/", {"sort": "price_asc", "page_size": 1}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["results"][0]["id"], self.product.pk)
        self.assertIsNotNone(response.data["next"])


class SellerCatalogTests(TestCase):
    def setUp(self):
        MarketplaceCatalogTests.setUp(self)
        self.client.force_authenticate(self.seller)
        self.foreign_seller = get_user_model().objects.create_user(
            "other@example.test", "password"
        )
        self.foreign_seller.is_seller = True
        self.foreign_seller.save()
        self.foreign_product = Product.objects.create(
            seller=self.foreign_seller,
            name="Foreign",
            description="Private",
            status="pending",
        )
        self.foreign_variant = ProductVariant.objects.create(
            product=self.foreign_product, size="S", color="Red", price=50, stock=5
        )

    def test_seller_catalog_is_owner_scoped_and_includes_pending(self):
        self.product.status = "pending"
        self.product.save()
        response = self.client.get("/api/seller/catalog/", {"status": "pending"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in response.data["results"]], [self.product.pk])
        summary = self.client.get("/api/seller/catalog/summary/").data
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["pending"], 1)

    def test_cannot_read_or_modify_another_sellers_product_or_variant(self):
        for method in ("get", "patch"):
            response = getattr(self.client, method)(
                f"/api/seller/catalog/{self.foreign_product.pk}/",
                {"name": "Changed"},
                format="json",
            )
            self.assertEqual(response.status_code, 404)
        response = self.client.patch(
            f"/api/seller/inventory/{self.foreign_variant.pk}/",
            {"stock": 99},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.foreign_variant.refresh_from_db()
        self.assertEqual(self.foreign_variant.stock, 5)

    def test_content_edit_requires_approval_and_keeps_slug(self):
        slug = self.product.slug
        response = self.client.patch(
            f"/api/seller/catalog/{self.product.pk}/",
            {"name": "New shirt", "status": "approved"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["slug"], slug)

    def test_pause_preserves_approval_and_invalidates_cache(self):
        url = f"/api/products/{self.product.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/seller/catalog/{self.product.pk}/",
                {"is_active": False},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "approved")
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_price_stock_updates_and_validation(self):
        url = f"/api/seller/inventory/{self.blue.pk}/"
        response = self.client.patch(
            url, {"stock": 8, "price": "299.50"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.blue.refresh_from_db()
        self.assertEqual(self.blue.price, 299.5)
        self.assertEqual(self.blue.stock, 8)
        for body in [{"stock": -1}, {"price": "0"}, {}, {"price": "NaN"}]:
            self.assertEqual(
                self.client.patch(url, body, format="json").status_code, 400
            )

    def test_customer_and_anonymous_cannot_manage_catalog(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get("/api/seller/catalog/").status_code, (401, 403))
        customer = get_user_model().objects.create_user(
            "customer@example.test", "password"
        )
        self.client.force_authenticate(customer)
        self.assertEqual(self.client.get("/api/seller/catalog/").status_code, 403)

    def test_return_policy_edit_validation(self):
        url = f"/api/seller/catalog/{self.product.pk}/"
        self.assertEqual(
            self.client.patch(
                url, {"return_policy": "return_and_exchange"}, format="json"
            ).status_code,
            400,
        )
        response = self.client.patch(
            url,
            {"return_policy": "return_and_exchange", "return_days": 7},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["return_days"], 7)
