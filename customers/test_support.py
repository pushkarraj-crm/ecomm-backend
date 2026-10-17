from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from .models import SupportTicket


class SupportTests(TestCase):
    def test_tickets_require_login_and_are_owner_scoped(self):
        user = get_user_model().objects.create_user(
            "support@example.test", "test-password"
        )
        other = get_user_model().objects.create_user(
            "private@example.test", "test-password"
        )
        SupportTicket.objects.create(
            user=other, subject="Private", message="Private message"
        )
        client = APIClient()
        self.assertEqual(client.get("/api/customer/support/").status_code, 401)
        client.force_authenticate(user)
        self.assertEqual(client.get("/api/customer/support/").data, [])
        result = client.post(
            "/api/customer/support/",
            {"subject": "Order question", "message": "Please help with my order"},
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(len(client.get("/api/customer/support/").data), 1)
