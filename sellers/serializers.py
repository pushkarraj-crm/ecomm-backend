from rest_framework import serializers

from orders.models import Refund, SellerOrder
from products.models import ProductVariant

from .models import Payout, SellerProfile


class SellerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerProfile
        fields = '__all__'


class KYCSubmissionSerializer(serializers.Serializer):
    pan = serializers.CharField(max_length=20)
    aadhaar = serializers.CharField(max_length=20)
    document = serializers.FileField()


class BankDetailsInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    account = serializers.CharField(max_length=50)
    ifsc = serializers.CharField(max_length=20)


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
