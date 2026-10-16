from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from .models import Product, ProductVariant, Review, DeliveryArea, StoreBanner
from .serializers import ProductVariantWriteSerializer

class StorefrontFeaturesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.seller = get_user_model().objects.create_user('catalog@example.test', 'test-password')
        self.product = Product.objects.create(seller=self.seller, name='Lamp', description='Desk lamp', status='approved')

    def test_reviews_are_public_but_identity_is_private(self):
        Review.objects.create(product=self.product, user=self.seller, rating=4, comment='Works well')
        data = self.client.get(f'/api/products/{self.product.pk}/').data
        self.assertEqual(data['reviews'][0]['comment'], 'Works well')
        self.assertNotIn('user', data['reviews'][0])
        self.assertNotIn('email', str(data['reviews']))

    def test_original_price_cannot_undercut_sale_price(self):
        serializer = ProductVariantWriteSerializer(data={'size':'M','color':'Blue','price':100,'original_price':90,'stock':2})
        self.assertFalse(serializer.is_valid())
        self.assertIn('original_price', serializer.errors)

    def test_delivery_needs_configured_active_pincode(self):
        self.assertEqual(self.client.get('/api/products/delivery/?postal_code=abc').status_code,400)
        self.assertFalse(self.client.get('/api/products/delivery/?postal_code=110001').data['available'])
        DeliveryArea.objects.create(postal_code='110001', city='New Delhi', min_days=2, max_days=5)
        result=self.client.get('/api/products/delivery/?postal_code=110001')
        self.assertTrue(result.data['available'])
        self.assertEqual(result.data['city'],'New Delhi')

    def test_inactive_banners_are_not_published(self):
        StoreBanner.objects.create(title='Published')
        StoreBanner.objects.create(title='Draft',is_active=False)
        result=self.client.get('/api/products/store-content/')
        self.assertEqual([b['title'] for b in result.data['banners']],['Published'])
