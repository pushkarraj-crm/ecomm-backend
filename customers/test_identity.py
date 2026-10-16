from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from customers.models import CustomerProfile

class CustomerIdentityTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('identity@example.test','test-password')
        self.client=APIClient()

    def test_login_returns_saved_name_and_mobile(self):
        CustomerProfile.objects.create(user=self.user,name='Customer Name',mobile_number='9876543210')
        response=self.client.post('/api/auth/customer/login/',{'email':self.user.email,'password':'test-password'},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['name'],'Customer Name')
        self.assertEqual(response.data['mobile_number'],'9876543210')
        self.assertIn('access',response.data)

    def test_missing_profile_can_be_completed_without_an_address(self):
        self.client.force_authenticate(self.user)
        response=self.client.post('/api/customer/profile/',{'name':'Saved Customer','mobile_number':'9876543210'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['name'],'Saved Customer')
        self.assertEqual(response.data['addresses'],[])

    def test_name_and_mobile_updates_do_not_remove_addresses(self):
        profile=CustomerProfile.objects.create(user=self.user,name='Before',mobile_number='9876543210')
        profile.addresses.create(address='Existing delivery address',is_default=True)
        self.client.force_authenticate(self.user)
        response=self.client.patch('/api/customer/profile/',{'name':'After'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['name'],'After')
        self.assertEqual(profile.addresses.count(),1)

    def test_no_profile_does_not_invent_a_customer_name(self):
        response=self.client.post('/api/auth/customer/login/',{'email':self.user.email,'password':'test-password'},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['name'],'')
