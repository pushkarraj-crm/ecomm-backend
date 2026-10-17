from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from .models import AdminEmployee, AdminInvitation

PASSWORD='Q7!mP4vK9@fR2dL6'
NEW_PASSWORD='M9!pL4rT7@qV2nC6'

class EmployeeAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner=get_user_model().objects.create_superuser('owner@example.test',PASSWORD)
        self.client=APIClient()
        self.client.force_authenticate(self.owner)
        self.base='/api/superadmin/'

    def create_employee(self,email='employee@example.test'):
        response=self.client.post(self.base+'resources/employees/',{'full_name':'Team Member','email':email,'password':PASSWORD,'is_active':True},format='json')
        self.assertEqual(response.status_code,201,response.data)
        return response.data

    def employee_client(self,email='employee@example.test',password=PASSWORD):
        client=APIClient()
        response=client.post(self.base+'login/',{'email':email,'password':password})
        self.assertEqual(response.status_code,200,response.data)
        self.assertTrue(response.data['is_employee'])
        self.assertFalse(response.data['is_superuser'])
        client.credentials(HTTP_AUTHORIZATION='Bearer '+response.data['access'])
        return client

    def test_owner_can_add_multiple_employees_without_granting_superuser(self):
        for email in ['one@example.test','two@example.test']:
            result=self.create_employee(email)
            self.assertNotIn('password',result)
            user=get_user_model().objects.get(email=email)
            self.assertTrue(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertFalse(user.is_customer)
            self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(AdminEmployee.objects.count(),2)
        duplicate=self.client.post(self.base+'resources/employees/',{'full_name':'Duplicate','email':'ONE@example.test','password':PASSWORD},format='json')
        self.assertEqual(duplicate.status_code,400)

    def test_employee_has_workspace_access_but_cannot_manage_accounts_or_invites(self):
        employee=self.create_employee()
        client=self.employee_client()
        for path in ['me/','overview/','resources/sellers/','resources/products/','resources/categories/','resources/orders/','resources/support/','resources/coupons/','resources/activity/']:
            self.assertEqual(client.get(self.base+path).status_code,200,path)
        for resource in ['employees','admin-invites']:
            self.assertEqual(client.get(self.base+'resources/'+resource+'/').status_code,403)
            self.assertEqual(client.post(self.base+'resources/'+resource+'/',{'email':'bad@example.test'}).status_code,403)
        self.assertEqual(client.patch(self.base+f"resources/employees/{employee['id']}/",{'is_superuser':True}).status_code,403)
        self.assertEqual(self.client.patch(self.base+f"resources/employees/{employee['id']}/",{'is_superuser':True}).status_code,400)

    def test_password_reset_revokes_old_employee_sessions(self):
        employee=self.create_employee()
        client=self.employee_client()
        result=self.client.patch(self.base+f"resources/employees/{employee['id']}/",{'password':NEW_PASSWORD},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(client.get(self.base+'me/').status_code,403)
        self.employee_client(password=NEW_PASSWORD)
        self.assertFalse(LogEntry.objects.filter(change_message__contains=NEW_PASSWORD).exists())

    def test_deactivate_then_reactivate_does_not_restore_old_tokens(self):
        employee=self.create_employee()
        client=self.employee_client()
        url=self.base+f"resources/employees/{employee['id']}/"
        self.assertEqual(self.client.patch(url,{'is_active':False}).status_code,200)
        self.assertEqual(client.get(self.base+'me/').status_code,401)
        self.assertEqual(self.client.patch(url,{'is_active':True}).status_code,200)
        self.assertEqual(client.get(self.base+'me/').status_code,403)
        self.employee_client()

    def test_generic_login_token_cannot_bypass_employee_session_checks(self):
        self.create_employee()
        client=APIClient()
        result=client.post('/api/auth/login/',{'email':'employee@example.test','password':PASSWORD})
        self.assertEqual(result.status_code,200)
        client.credentials(HTTP_AUTHORIZATION='Bearer '+result.data['access'])
        self.assertEqual(client.get(self.base+'overview/').status_code,403)


class SuperAdminSignupTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner=get_user_model().objects.create_superuser('inviter@example.test',PASSWORD)
        self.admin=APIClient()
        self.admin.force_authenticate(self.owner)
        self.client=APIClient()
        self.base='/api/superadmin/'

    def invitation(self):
        response=self.admin.post(self.base+'resources/admin-invites/',{'email':'new-admin@example.test'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertTrue(response.data['signup_token'])
        return response.data

    def signup(self,token,email='new-admin@example.test'):
        return self.client.post(self.base+'signup/',{'email':email,'password':NEW_PASSWORD,'token':token})

    def test_invitation_creates_a_superadmin_once_and_never_lists_plain_token(self):
        invite=self.invitation()
        stored=AdminInvitation.objects.get(pk=invite['id'])
        self.assertNotEqual(stored.token_hash,invite['signup_token'])
        listed=self.admin.get(self.base+'resources/admin-invites/').data['results'][0]
        self.assertIsNone(listed['signup_token'])
        response=self.signup(invite['signup_token'])
        self.assertEqual(response.status_code,201,response.data)
        user=get_user_model().objects.get(email='new-admin@example.test')
        self.assertTrue(user.is_superuser and user.is_staff)
        self.assertFalse(user.is_customer)
        self.assertEqual(self.signup(invite['signup_token']).status_code,400)
        self.assertFalse(LogEntry.objects.filter(change_message__contains=invite['signup_token']).exists())

    def test_signup_requires_matching_email_and_valid_invitation(self):
        invite=self.invitation()
        self.assertEqual(self.signup(invite['signup_token'],'wrong@example.test').status_code,400)
        self.assertEqual(self.signup('x'*43).status_code,400)
        self.assertEqual(self.client.post(self.base+'signup/',{'email':'bad@example.test','password':NEW_PASSWORD}).status_code,400)
        self.assertFalse(get_user_model().objects.filter(email='new-admin@example.test').exists())

    def test_expired_revoked_and_disabled_creator_invitations_are_rejected(self):
        invite=self.invitation()
        stored=AdminInvitation.objects.get(pk=invite['id'])
        stored.expires_at=timezone.now()-timedelta(seconds=1)
        stored.save()
        self.assertEqual(self.signup(invite['signup_token']).status_code,400)
        stored.expires_at=timezone.now()+timedelta(hours=1)
        stored.is_active=False
        stored.save()
        self.assertEqual(self.signup(invite['signup_token']).status_code,400)
        stored.is_active=True
        stored.save()
        self.owner.is_superuser=False
        self.owner.save()
        self.assertEqual(self.signup(invite['signup_token']).status_code,400)
