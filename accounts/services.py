from django.db import transaction
from django.conf import settings
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator

from .models import User
from .selectors import get_active_user_by_email
from customers.services import save_customer_profile
from sellers.services import create_seller_profile


class UserService:

    @staticmethod
    @transaction.atomic
    def create_customer(data):
        user = User.objects.create_user(
            email=data.get('email'),
            password=data.get('password')
        )
        profile_fields = {'name', 'mobile_number'}
        if profile_fields.issubset(data):
            profile_data = {field: data[field] for field in profile_fields}
            if 'addresses' in data:
                profile_data['addresses'] = data['addresses']
            save_customer_profile(
                user,
                profile_data,
            )
        return user

    @staticmethod
    @transaction.atomic
    def create_seller(data):
        user = User.objects.create_user(
            email=data.get('email'),
            password=data.get('password')
        )
        user.is_seller = True
        user.is_customer = False
        user.seller_status = 'pending'
        user.save(update_fields=['is_seller', 'is_customer', 'seller_status'])

        create_seller_profile(user, data.get('business_name') or user.email)
        return user

    @staticmethod
    def approve_seller(user):
        user.seller_status = 'approved'
        user.save(update_fields=['seller_status'])
        return user

    @staticmethod
    def blacklist_user(user):
        user.is_blacklisted = True
        user.save(update_fields=['is_blacklisted'])
        return user

    @staticmethod
    def request_password_reset(email, reset_url):
        user = get_active_user_by_email(email)
        if user is None:
            return

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        message = (
            'A password reset was requested for this account.\n\n'
            f'Use this endpoint: {reset_url}\n'
            'Send a POST request with this JSON body:\n'
            f'{{"uid": "{uid}", "token": "{token}", '
            '"new_password": "your new password"}\n\n'
            'If you did not request this change, ignore this email.'
        )
        send_mail(
            subject='Reset your Marketplace password',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

    @staticmethod
    @transaction.atomic
    def reset_password(user, new_password):
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )

        user.set_password(new_password)
        user.save(update_fields=['password'])
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)

    @staticmethod
    def logout(refresh_token):
        from rest_framework_simplejwt.tokens import RefreshToken

        RefreshToken(refresh_token).blacklist()
