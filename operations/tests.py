from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from rest_framework.test import APIClient
from products.models import Category, DeliveryArea, Product
from customers.models import SupportTicket

class SuperAdminTests(TestCase):
    def setUp(self):
        users=get_user_model().objects
        self.admin=users.create_superuser('admin@example.test','strong-admin-password')
        self.customer=users.create_user('customer@example.test','strong-test-password')
        self.seller=users.create_user('seller@example.test','strong-test-password')
        self.seller.is_seller=True
        self.seller.save()
        self.client=APIClient()
        self.base='/api/superadmin/'

    def test_login_rejects_customer_seller_and_staff_only_accounts(self):
        for user in [self.customer,self.seller]:
            response=self.client.post(self.base+'login/',{'email':user.email,'password':'strong-test-password'})
            self.assertEqual(response.status_code,401)
            self.assertNotIn('access',response.data)
        self.customer.is_staff=True
        self.customer.save()
        self.assertEqual(self.client.post(self.base+'login/',{'email':self.customer.email,'password':'strong-test-password'}).status_code,401)
        response=self.client.post(self.base+'login/',{'email':self.admin.email,'password':'strong-admin-password'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.data['is_superuser'])

    def test_every_resource_requires_superuser_on_every_request(self):
        paths=['overview/','me/']+['resources/'+name+'/' for name in ['sellers','customers','products','categories','orders','requests','support','coupons','delivery','banners','inventory','refunds','payouts','activity']]
        for path in paths:
            self.assertEqual(self.client.get(self.base+path).status_code,401)
        self.client.force_authenticate(self.customer)
        for path in paths:
            self.assertEqual(self.client.get(self.base+path).status_code,403)
        self.client.force_authenticate(self.admin)
        for path in paths:
            self.assertEqual(self.client.get(self.base+path).status_code,200,path)

    def test_seller_approval_is_audited_and_cannot_escalate_privileges(self):
        self.client.force_authenticate(self.admin)
        url=self.base+f'resources/sellers/{self.seller.pk}/'
        self.assertEqual(self.client.patch(url,{'is_superuser':True}).status_code,400)
        self.assertEqual(self.client.patch(url,{'seller_status':'approved'}).status_code,200)
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.seller_status,'approved')
        self.assertFalse(self.seller.is_superuser)
        self.assertEqual(LogEntry.objects.get().user,self.admin)
        self.assertNotIn('password',str(self.client.get(self.base+'resources/sellers/').data))

    def test_category_cycles_and_invalid_delivery_ranges_are_rejected(self):
        self.client.force_authenticate(self.admin)
        parent=Category.objects.create(name='Parent')
        child=Category.objects.create(name='Child',parent=parent)
        self.assertEqual(self.client.patch(self.base+f'resources/categories/{parent.pk}/',{'parent':child.pk}).status_code,400)
        response=self.client.post(self.base+'resources/delivery/',{'postal_code':'110001','city':'Delhi','min_days':8,'max_days':2})
        self.assertEqual(response.status_code,400)
        self.assertEqual(DeliveryArea.objects.count(),0)

    def test_support_response_and_product_approval_work(self):
        self.client.force_authenticate(self.admin)
        ticket=SupportTicket.objects.create(user=self.customer,subject='Order help',message='Help with order')
        response=self.client.patch(self.base+f'resources/support/{ticket.pk}/',{'status':'answered','response':'Please check order history.'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['status'],'answered')
        product=Product.objects.create(seller=self.seller,name='Test product',description='Test')
        response=self.client.patch(self.base+f'resources/products/{product.pk}/',{'status':'approved'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['status'],'approved')

    def test_financial_records_and_admin_accounts_are_not_arbitrarily_editable(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(self.base+'resources/orders/1/',{'status':'paid'}).status_code,405)
        self.assertEqual(self.client.get(self.base+f'resources/customers/{self.admin.pk}/').status_code,404)
        self.assertEqual(self.client.post(self.base+'resources/sellers/',{'email':'new@example.test'}).status_code,405)

    def test_disabled_admin_loses_access_even_with_existing_token(self):
        self.client.force_authenticate(self.admin)
        self.admin.is_superuser=False
        self.admin.save()
        self.assertEqual(self.client.get(self.base+'overview/').status_code,403)
