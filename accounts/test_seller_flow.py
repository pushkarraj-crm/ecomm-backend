from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from sellers.models import SellerProfile


class SellerRegistrationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.payload = {
            "email": "new-seller@example.test",
            "password": "Seller-Test-Password123!",
            "owner_full_name": "Test Owner",
            "business_name": "Legal Business",
            "store_name": "My Store",
            "business_type": "individual",
            "gst_registered": False,
        }

    def test_register_then_login_then_open_dashboard(self):
        response = self.client.post(
            "/api/auth/seller/register/", self.payload, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("access", response.data)
        user = get_user_model().objects.get(email=self.payload["email"])
        self.assertTrue(user.is_seller)
        self.assertEqual(user.seller_status, "pending")
        profile = SellerProfile.objects.get(user=user)
        self.assertEqual(profile.store_name, "My Store")
        self.assertEqual(profile.owner_full_name, "Test Owner")
        login = self.client.post(
            "/api/auth/seller/login/",
            {k: self.payload[k] for k in ("email", "password")},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.assertTrue(login.data["is_seller"])
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access"])
        self.assertEqual(self.client.get("/api/seller/dashboard/").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/seller/catalog/single/", {}, format="json"
            ).status_code,
            403,
        )

    def test_existing_email_returns_field_validation_instead_of_server_error(self):
        get_user_model().objects.create_user(self.payload["email"], "password")
        response = self.client.post(
            "/api/auth/seller/register/", self.payload, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)
        self.assertEqual(
            get_user_model().objects.filter(email=self.payload["email"]).count(), 1
        )

    def test_gst_and_business_type_validation(self):
        for changes in [
            {"gst_registered": True},
            {"gst_registered": False, "gst_number": "27AAPFU0939F1ZV"},
            {"business_type": "invalid"},
        ]:
            response = self.client.post(
                "/api/auth/seller/register/", {**self.payload, **changes}, format="json"
            )
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(
            get_user_model().objects.filter(email=self.payload["email"]).exists()
        )

    def test_customer_cannot_use_seller_login_or_dashboard(self):
        get_user_model().objects.create_user(
            self.payload["email"], self.payload["password"]
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/seller/login/", self.payload, format="json"
            ).status_code,
            400,
        )
        self.assertIn(self.client.get("/api/seller/dashboard/").status_code, (401, 403))
