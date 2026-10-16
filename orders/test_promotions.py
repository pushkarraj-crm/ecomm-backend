from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from cart.models import Cart, CartItem
from products.models import Product, ProductVariant
from .models import Coupon
from .promotions import price_cart
from .services import create_order_from_cart

class PromotionTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.buyer=users.create_user('coupon-buyer@example.test','test-password')
        self.seller=users.create_user('coupon-seller@example.test','test-password')
        self.seller.is_seller=True
        self.seller.save()
        other=users.create_user('coupon-other@example.test','test-password')
        self.cart=Cart.objects.create(user=self.buyer)
        self.items=[]
        for seller in [self.seller,other]:
            p=Product.objects.create(seller=seller,name=f'Item {seller.id}',description='Test',status='approved')
            v=ProductVariant.objects.create(product=p,size='M',color='Blue',stock=10,price=100)
            self.items.append(CartItem.objects.create(cart=self.cart,product_variant=v,quantity=2))
        self.coupon=Coupon.objects.create(code='save10',seller=self.seller,percent=10,minimum_subtotal=100,starts_at=timezone.now()-timedelta(days=1),expires_at=timezone.now()+timedelta(days=1),is_active=True)

    def test_discount_only_affects_eligible_seller_and_uses_integer_paise(self):
        result=price_cart(self.items,'save10')
        self.assertEqual(result['subtotal_paise'],40000)
        self.assertEqual(result['total_paise'],38000)
        self.assertEqual(result['prices'][self.items[0].pk],9000)
        self.assertEqual(result['prices'][self.items[1].pk],10000)

    def test_expired_or_ineligible_coupons_are_rejected(self):
        self.coupon.expires_at=timezone.now()-timedelta(hours=1)
        self.coupon.save()
        with self.assertRaises(ValidationError):
            price_cart(self.items,'SAVE10')

    def test_checkout_totals_and_seller_earnings_match_discounted_items(self):
        order=create_order_from_cart(self.buyer,{'name':'Buyer','phone':'9000000000','address':'Test address','coupon_code':'SAVE10'})
        self.assertEqual(order.total_amount,380)
        self.assertEqual(order.discount_amount,20)
        self.assertEqual(order.seller_orders.get(seller=self.seller).total_amount,180)
        self.assertEqual(order.seller_orders.get(seller=self.seller).items.first().price,90)

    def test_preview_and_checkout_match_without_trusting_client_amount(self):
        client=APIClient()
        client.force_authenticate(self.buyer)
        result=client.post('/api/orders/coupon/preview/',{'coupon_code':'SAVE10','total':1})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.data['total'],380)
