from rest_framework import serializers
import re

from orders.models import Refund, SellerOrder
from products.models import ProductVariant

from .models import BankAccount, Payout, SellerProfile


class SellerProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = SellerProfile
        fields = [
            'id', 'email', 'business_name', 'store_name', 'owner_full_name',
            'business_type', 'gst_registered', 'gst_number', 'gst_legal_name',
            'gst_verification_status', 'gst_verified_at', 'gst_registered_address',
            'use_gst_registered_address', 'pickup_address_line_1',
            'pickup_address_line_2', 'pickup_landmark', 'pickup_city',
            'pickup_state', 'pickup_postal_code', 'pickup_country',
            'is_kyc_verified',
        ]
        read_only_fields = [
            'id', 'email', 'business_name', 'gst_legal_name',
            'gst_verification_status', 'gst_verified_at',
            'gst_registered_address', 'is_kyc_verified',
        ]

    def validate(self, attrs):
        instance = self.instance
        gst_registered = attrs.get(
            'gst_registered',
            instance.gst_registered if instance else False,
        )
        gst_number = attrs.get(
            'gst_number',
            (instance.gst_number or '') if instance else '',
        )
        gst_number = (gst_number or '').strip().upper()
        if gst_registered and not gst_number:
            raise serializers.ValidationError({'gst_number': 'Required when GST is enabled.'})
        if not gst_registered and attrs.get('gst_number'):
            raise serializers.ValidationError({'gst_number': 'Leave blank when GST is disabled.'})
        if gst_number and not re.fullmatch(
            r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]',
            gst_number,
        ):
            raise serializers.ValidationError({'gst_number': 'Enter a valid 15-character GSTIN.'})
        if 'gst_number' in attrs or (instance and not gst_registered):
            attrs['gst_number'] = gst_number or None

        use_registered_address = attrs.get(
            'use_gst_registered_address',
            instance.use_gst_registered_address if instance else False,
        )
        if use_registered_address:
            if not gst_registered:
                attrs['use_gst_registered_address'] = False
                use_registered_address = False
            elif not instance or instance.gst_verification_status != 'verified' or not instance.gst_registered_address:
                raise serializers.ValidationError({
                    'use_gst_registered_address': 'Verify GST before using its registered address.',
                })
        if not use_registered_address and any(
            attrs.get(field, getattr(instance, field, '') if instance else '')
            for field in ('pickup_address_line_1', 'pickup_city', 'pickup_state', 'pickup_postal_code')
        ):
            required = ('pickup_address_line_1', 'pickup_city', 'pickup_state', 'pickup_postal_code')
            missing = [
                field for field in required
                if not attrs.get(field, getattr(instance, field, '') if instance else '')
            ]
            if missing:
                raise serializers.ValidationError({field: 'Required for a pickup address.' for field in missing})
        return attrs

    def update(self, instance, validated_data):
        previous_gst_number = instance.gst_number or ''
        previous_gst_registered = instance.gst_registered
        gst_number = validated_data.get('gst_number', previous_gst_number)
        gst_registered = validated_data.get('gst_registered', previous_gst_registered)
        if 'store_name' in validated_data:
            validated_data['business_name'] = validated_data['store_name']

        if not gst_registered:
            validated_data.update({
                'gst_number': None,
                'gst_legal_name': '',
                'gst_verification_status': 'not_required',
                'gst_verified_at': None,
                'gst_registered_address': {},
                'use_gst_registered_address': False,
            })
        elif gst_number != previous_gst_number or gst_registered != previous_gst_registered:
            validated_data.update({
                'gst_legal_name': '',
                'gst_verification_status': 'pending',
                'gst_verified_at': None,
                'gst_registered_address': {},
                'use_gst_registered_address': False,
            })
        return super().update(instance, validated_data)


class KYCSubmissionSerializer(serializers.Serializer):
    pan = serializers.CharField(max_length=20)
    aadhaar = serializers.CharField(max_length=20)
    document = serializers.FileField()


class BankDetailsInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, trim_whitespace=True)
    account = serializers.RegexField(regex=r'^[A-Za-z0-9]{5,35}$', max_length=35)
    confirm_account = serializers.RegexField(regex=r'^[A-Za-z0-9]{5,35}$', max_length=35)
    ifsc = serializers.RegexField(regex=r'^[A-Za-z]{4}0[A-Za-z0-9]{6}$', max_length=11)

    def validate(self, attrs):
        attrs['account'] = attrs['account'].strip()
        attrs['confirm_account'] = attrs['confirm_account'].strip()
        attrs['ifsc'] = attrs['ifsc'].strip().upper()
        if attrs['account'] != attrs['confirm_account']:
            raise serializers.ValidationError({'confirm_account': 'Account numbers do not match.'})
        return attrs


class BankAccountReadSerializer(serializers.ModelSerializer):
    masked_account_number = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = [
            'account_holder_name', 'masked_account_number', 'ifsc_code',
            'verification_status', 'verified_at',
        ]

    def get_masked_account_number(self, instance):
        return f"{'*' * max(len(instance.account_number) - 4, 0)}{instance.account_number[-4:]}"


class BankVerificationAmountSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=3, decimal_places=2, min_value=1, max_value=2)


class PayoutRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)


class SellerEarningSerializer(serializers.ModelSerializer):
    seller_order_id = serializers.IntegerField(source='id', read_only=True)
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    amount = serializers.SerializerMethodField()
    order_status = serializers.CharField(source='order.status', read_only=True)
    fulfillment_status = serializers.CharField(source='status', read_only=True)
    paid_at = serializers.DateTimeField(source='order.payment.updated_at', read_only=True)

    class Meta:
        model = SellerOrder
        fields = [
            'seller_order_id', 'order_id', 'amount', 'order_status',
            'fulfillment_status', 'paid_at',
        ]

    def get_amount(self, instance):
        return round(float(instance.total_amount), 2)


class SellerPayoutHistorySerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = ['id', 'amount', 'status', 'created_at']

    def get_amount(self, instance):
        return round(float(instance.amount), 2)


class SellerInventoryVariantSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ProductVariant
        fields = ['id', 'product_id', 'product_name', 'size', 'color', 'price', 'stock']


class InventoryStockUpdateSerializer(serializers.Serializer):
    stock = serializers.IntegerField(min_value=0)


class SellerRefundRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    reason = serializers.CharField(max_length=255, trim_whitespace=True)
    idempotency_key = serializers.CharField(min_length=8, max_length=64, trim_whitespace=True)


class SellerRefundSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Refund
        fields = ['id', 'amount', 'reason', 'status', 'razorpay_refund_id', 'failure_reason', 'created_at']

    def get_amount(self, instance):
        return round(instance.amount_paise / 100, 2)
