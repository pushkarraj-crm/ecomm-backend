from rest_framework import serializers
from .models import Payment, Refund, SellerOrder, OrderItem, Order


class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.CharField(source='product_variant.__str__')
    variant_id = serializers.IntegerField(source='product_variant_id', read_only=True)
    product_name = serializers.CharField(source='product_variant.product.name', read_only=True)
    size = serializers.CharField(source='product_variant.size', read_only=True)
    color = serializers.CharField(source='product_variant.color', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['product', 'variant_id', 'product_name', 'size', 'color', 'quantity', 'price']


class SellerRefundSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Refund
        fields = ['id', 'amount', 'reason', 'status', 'failure_reason', 'created_at']

    def get_amount(self, instance):
        return round(instance.amount_paise / 100, 2)


class SellerOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    order_id = serializers.IntegerField(read_only=True)
    order_status = serializers.CharField(source='order.status', read_only=True)
    payment_status = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source='order.created_at', read_only=True)
    customer = serializers.SerializerMethodField()
    refunds = SellerRefundSerializer(many=True, read_only=True)

    class Meta:
        model = SellerOrder
        fields = [
            'id', 'order_id', 'seller', 'total_amount', 'status', 'order_status',
            'payment_status', 'created_at', 'customer', 'items', 'refunds',
        ]

    def get_payment_status(self, seller_order):
        try:
            return seller_order.order.payment.status
        except Payment.DoesNotExist:
            return 'paid'

    def get_customer(self, seller_order):
        order = seller_order.order
        address = {
            'address_line_1': order.address_line_1,
            'address_line_2': order.address_line_2,
            'landmark': order.landmark,
            'city': order.city,
            'state': order.state,
            'postal_code': order.postal_code,
            'country': order.country,
            'address': order.address,
        }
        return {
            'name': order.name,
            'phone': order.phone,
            'email': order.email,
            'address': address,
        }

class OrderSerializer(serializers.ModelSerializer):
    seller_orders = SellerOrderSerializer(many=True)
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id',
            'name',
            'phone',
            'email',
            'address',
            'address_line_1',
            'address_line_2',
            'landmark',
            'city',
            'state',
            'postal_code',
            'country',
            'total_amount',
            'created_at',
            'status',
            'payment_status',
            'seller_orders'
        ]

    def get_payment_status(self, order):
        try:
            return order.payment.status
        except Payment.DoesNotExist:
            return 'paid'


class CheckoutSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=15)
    address_id = serializers.IntegerField(min_value=1, required=False)
    address = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        if ('address_id' in attrs) == ('address' in attrs):
            raise serializers.ValidationError(
                'Provide exactly one of address_id or address.'
            )
        return attrs


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SellerOrder.STATUS_CHOICES)


class VerifyPaymentSerializer(serializers.Serializer):
    order_id = serializers.IntegerField(min_value=1)
    razorpay_order_id = serializers.CharField(max_length=64)
    razorpay_payment_id = serializers.CharField(max_length=64)
    razorpay_signature = serializers.CharField(max_length=128)
