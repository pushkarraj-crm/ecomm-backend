from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from customers.serializers import CustomerAddressInputSerializer
from .selectors import get_active_user_by_id
from .services import UserService


class CustomerRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    name = serializers.CharField(max_length=255, required=False)
    mobile_number = serializers.CharField(max_length=20, required=False)
    addresses = CustomerAddressInputSerializer(
        many=True,
        required=False,
        allow_empty=False,
    )

    def validate(self, attrs):
        profile_fields = {'name', 'mobile_number'}
        supplied_profile_fields = profile_fields.intersection(attrs)
        if supplied_profile_fields and supplied_profile_fields != profile_fields:
            missing_fields = sorted(profile_fields - supplied_profile_fields)
            raise serializers.ValidationError({
                field: 'Required when creating a profile during signup.'
                for field in missing_fields
            })
        if 'addresses' in attrs and supplied_profile_fields != profile_fields:
            raise serializers.ValidationError({
                field: 'Required when adding profile details during signup.'
                for field in sorted(profile_fields - supplied_profile_fields)
            })
        addresses = attrs.get('addresses', [])
        if sum(address.get('is_default', False) for address in addresses) > 1:
            raise serializers.ValidationError({
                'addresses': 'Only one address can be the default.'
            })
        return attrs

    def create(self, data):
        return UserService.create_customer(data)


class SellerRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    business_name = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def create(self, data):
        return UserService.create_seller(data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])
        if user:
            data['user'] = user
            return data
        raise serializers.ValidationError("Invalid credentials")


class CustomerLoginSerializer(LoginSerializer):
    def validate(self, data):
        data = super().validate(data)
        if not data['user'].is_customer or data['user'].is_seller:
            raise serializers.ValidationError("Invalid credentials")
        return data


class SellerLoginSerializer(LoginSerializer):
    def validate(self, data):
        data = super().validate(data)
        if not data['user'].is_seller:
            raise serializers.ValidationError("Invalid credentials")
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs['uid']))
        except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
            user_id = None

        user = get_active_user_by_id(user_id) if user_id else None
        if user is None or not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError('The password reset link is invalid or expired.')

        try:
            validate_password(attrs['new_password'], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'new_password': error.messages})

        attrs['user'] = user
        return attrs

    def create(self, validated_data):
        UserService.reset_password(
            user=validated_data['user'],
            new_password=validated_data['new_password'],
        )
        return validated_data['user']


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        try:
            token = RefreshToken(value)
        except TokenError:
            raise serializers.ValidationError('Invalid or expired refresh token.')

        request = self.context['request']
        token_user_id = token.get(api_settings.USER_ID_CLAIM)
        if str(token_user_id) != str(request.user.pk):
            raise serializers.ValidationError('Refresh token does not belong to this user.')
        return value
