import csv, io
from datetime import timedelta
from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from orders.models import Order, SellerOrder, OrderItem, Payment, CustomerOrderRequest
from products.models import Product, ProductVariant


class OrderWorkspaceTests(TestCase):
    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.seller = users.create_user("orders-seller@example.test", "test-password")
        self.seller.is_seller = True
        self.seller.save()
        self.other = users.create_user("other-seller@example.test", "test-password")
        self.customer = users.create_user("buyer@example.test", "test-password")
        self.variant = ProductVariant.objects.create(
            product=Product.objects.create(
                seller=self.seller, name="=dangerous formula", description="Test"
            ),
            price=100,
            stock=2,
            size="M",
            color="Red",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.seller)
        self.url = "/api/seller/orders/workspace/"

    def order(self, seller=None, status="pending", tracking="", payment=None):
        order = Order.objects.create(
            user=self.customer,
            name="Buyer",
            phone="9999999999",
            email=self.customer.email,
            address="Test address",
            total_amount=100,
            status="paid",
        )
        row = SellerOrder.objects.create(
            order=order,
            seller=seller or self.seller,
            status=status,
            tracking_number=tracking,
            total_amount=100,
        )
        OrderItem.objects.create(
            seller_order=row, product_variant=self.variant, quantity=1, price=100
        )
        if payment:
            Payment.objects.create(order=order, status=payment, amount_paise=10000)
        return row

    def test_tabs_are_disjoint_owned_and_counted_across_pages(self):
        pending = self.order()
        self.order(tracking="TRACK-1")
        self.order(payment="pending")
        self.order(status="shipped")
        self.order(status="delivered")
        cancelled = self.order()
        CustomerOrderRequest.objects.create(
            seller_order=cancelled, kind="cancel", status="approved", reason="Cancel"
        )
        self.order(seller=self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["counts"],
            {
                "pending": 1,
                "ready_to_ship": 1,
                "on_hold": 1,
                "shipped": 1,
                "delivered": 1,
                "cancelled": 1,
            },
        )
        self.assertEqual([row["id"] for row in response.data["results"]], [pending.pk])
        SellerOrder.objects.filter(pk=pending.pk).update(
            created_at=timezone.now() - timedelta(days=3)
        )
        self.assertEqual(self.client.get(self.url).data["dispatch"]["overdue"], 1)

    def test_filters_exports_and_validation(self):
        row = self.order()
        response = self.client.get(
            self.url, {"search": row.order_id, "search_by": "order"}
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            self.client.get(
                self.url, {"search": self.variant.pk, "search_by": "sku"}
            ).data["count"],
            1,
        )
        self.assertEqual(
            self.client.get(self.url, {"start": "2099-01-01"}).data["count"], 0
        )
        response = self.client.get(self.url, {"export": "csv"})
        self.assertEqual(response.status_code, 200)
        lines = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertTrue(lines[1][3].startswith("'="))
        for params in [
            {"tab": "fake"},
            {"search": "abc"},
            {"search": "9" * 100},
            {"start": "2026-10-20", "end": "2026-10-01"},
        ]:
            self.assertEqual(self.client.get(self.url, params).status_code, 400)
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_pending_cancel_and_approved_return_do_not_count_as_cancellation(self):
        row = self.order()
        CustomerOrderRequest.objects.create(
            seller_order=row, kind="cancel", status="pending", reason="Cancel"
        )
        CustomerOrderRequest.objects.create(
            seller_order=row, kind="return", status="approved", reason="Return"
        )
        self.assertEqual(self.client.get(self.url).data["counts"]["cancelled"], 0)

    def test_details_resolve_independently_of_filters_and_reject_other_sellers(self):
        own = self.order(payment="pending")
        other = self.order(seller=self.other)
        response = self.client.get(f"/api/seller/orders/{own.pk}/details/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["id"], own.pk)
        self.assertEqual(
            self.client.get(f"/api/seller/orders/{other.pk}/details/").status_code, 404
        )
