from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Order, SellerOrder, OrderItem, CustomerOrderRequest
from products.models import Product, ProductVariant

class CustomerRequestTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.customer=users.create_user('buyer@example.test','test-password')
        self.other=users.create_user('other@example.test','test-password')
        self.seller=users.create_user('seller@example.test','test-password')
        self.seller.is_seller=True
        self.seller.save()
        self.order=Order.objects.create(user=self.customer,name='Buyer',phone='9000000000',email=self.customer.email,address='Test',status='paid',total_amount=100)
        self.part=SellerOrder.objects.create(order=self.order,seller=self.seller,total_amount=100)
        product=Product.objects.create(seller=self.seller,name='Lamp',description='Test',return_policy='return_and_exchange',return_days=7)
        variant=ProductVariant.objects.create(product=product,size='M',color='Blue',price=100,stock=1)
        OrderItem.objects.create(seller_order=self.part,product_variant=variant,quantity=1,price=100)
        self.client=APIClient()
        self.client.force_authenticate(self.customer)
        self.url=f'/api/orders/customer/shipments/{self.part.pk}/requests/'

    def test_customer_cannot_request_someone_elses_order(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(self.url,{'kind':'cancel','reason':'Please cancel this order'}).status_code,404)

    def test_cancellation_is_reviewed_and_idempotent(self):
        body={'kind':'cancel','reason':'Please cancel this order'}
        self.assertEqual(self.client.post(self.url,body).status_code,201)
        self.assertEqual(self.client.post(self.url,body).status_code,200)
        self.assertEqual(CustomerOrderRequest.objects.count(),1)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status,'paid')

    def test_return_requires_delivery_within_policy(self):
        body={'kind':'return','reason':'The item is damaged'}
        self.assertEqual(self.client.post(self.url,body).status_code,400)
        self.part.status='delivered'
        self.part.delivered_at=timezone.now()-timedelta(days=8)
        self.part.save()
        self.assertEqual(self.client.post(self.url,body).status_code,400)
        self.part.delivered_at=timezone.now()-timedelta(days=1)
        self.part.save()
        self.assertEqual(self.client.post(self.url,body).status_code,201)

    def test_tracking_is_seller_scoped_and_requires_https(self):
        url=f'/api/seller/orders/{self.part.pk}/tracking/'
        data={'carrier':'Carrier','tracking_number':'ABC','tracking_url':'https://example.com/track/ABC'}
        self.assertEqual(self.client.patch(url,data).status_code,403)
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.patch(url,{**data,'tracking_url':'javascript:alert(1)'}).status_code,400)
        self.assertEqual(self.client.patch(url,data).status_code,200)
