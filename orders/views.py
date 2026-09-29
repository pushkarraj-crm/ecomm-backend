import hashlib
import hmac
import json

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from django.http import Http404
from django.conf import settings
from django.db.models import Count, Q

from accounts.permissions import IsCustomer, IsSeller
from sellers.selectors import get_seller_earnings_summary, get_seller_inventory_summary
from .gateways.razorpay import RazorpayGatewayError
from .services import (
    PaymentVerificationError,
    create_razorpay_payment,
    update_seller_order_status,
    update_refund_status_by_gateway_id,
    verify_razorpay_payment,
)
from .selectors import (
    get_customer_orders,
    get_customer_payment,
    get_seller_order,
    get_seller_orders,
)
from .serializers import (
    CheckoutSerializer,
    OrderSerializer,
    OrderStatusUpdateSerializer,
    SellerOrderSerializer,
    VerifyPaymentSerializer,
)
from core.pagination import ProductPagination


class RazorpayWebhookAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        secret = settings.RAZORPAY_WEBHOOK_SECRET
        signature = request.headers.get('X-Razorpay-Signature', '')
        if not secret:
            return Response({'error': 'Razorpay webhook secret is not configured.'}, status=503)

        expected = hmac.new(
            secret.encode('utf-8'),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature):
            return Response({'error': 'Invalid webhook signature.'}, status=400)

        try:
            event_data = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({'error': 'Invalid webhook payload.'}, status=400)

        if not isinstance(event_data, dict):
            return Response({'error': 'Invalid webhook payload.'}, status=400)

        event = event_data.get('event')
        payload = event_data.get('payload') or {}
        if not isinstance(payload, dict):
            return Response({'error': 'Invalid webhook payload.'}, status=400)
        refund_container = payload.get('refund') or {}
        if not isinstance(refund_container, dict):
            return Response({'error': 'Invalid webhook payload.'}, status=400)
        refund_entity = refund_container.get('entity') or {}
        if not isinstance(refund_entity, dict):
            return Response({'error': 'Invalid webhook payload.'}, status=400)
        refund_error = refund_entity.get('error') or {}
        if not isinstance(refund_error, dict):
            refund_error = {}
        status_by_event = {
            'refund.created': 'pending',
            'refund.processed': 'processed',
            'refund.failed': 'failed',
        }
        if event in status_by_event and refund_entity.get('id'):
            update_refund_status_by_gateway_id(
                razorpay_refund_id=refund_entity['id'],
                status=status_by_event[event],
                failure_reason=(
                    refund_entity.get('error_description')
                    or refund_error.get('description')
                    or ''
                ),
            )
        return Response({'received': True})


# =========================
# CHECKOUT
# =========================
class CheckoutView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order, payment = create_razorpay_payment(
                request.user,
                serializer.validated_data,
            )
        except RazorpayGatewayError as error:
            return Response({'error': str(error)}, status=error.status_code)

        return Response({
            "message": "Payment initiated",
            "order_id": order.id,
            "order_status": order.status,
            "total": order.total_amount,
            "payment": {
                'provider': 'razorpay',
                'key_id': settings.RAZORPAY_KEY_ID,
                'razorpay_order_id': payment.razorpay_order_id,
                'amount': payment.amount_paise,
                'currency': payment.currency,
            },
        }, status=status.HTTP_201_CREATED)


class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = get_customer_payment(
            customer=request.user,
            order_id=serializer.validated_data['order_id'],
        )
        if payment is None:
            raise Http404

        try:
            order = verify_razorpay_payment(
                payment=payment,
                razorpay_order_id=serializer.validated_data['razorpay_order_id'],
                razorpay_payment_id=serializer.validated_data['razorpay_payment_id'],
                signature=serializer.validated_data['razorpay_signature'],
            )
        except (PaymentVerificationError, RazorpayGatewayError) as error:
            return Response({'error': str(error)}, status=error.status_code)

        return Response({
            'message': 'Payment verified and order confirmed.',
            'order_id': order.id,
            'order_status': order.status,
            'payment_status': 'paid',
        })


# =========================
# SELLER DASHBOARD
# =========================
class SellerDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        user = request.user
        orders = get_seller_orders(user)
        counts = orders.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            shipped=Count('id', filter=Q(status='shipped')),
            delivered=Count('id', filter=Q(status='delivered')),
        )

        # Keep the dashboard response light; the dedicated orders endpoint is
        # paginated for browsing the complete history.
        serializer = SellerOrderSerializer(orders[:10], many=True)
        earnings = get_seller_earnings_summary(user)
        inventory = get_seller_inventory_summary(
            user,
            low_stock_threshold=settings.LOW_STOCK_THRESHOLD,
        )

        return Response({
            "seller": user.email,
            "total_orders": counts['total'],
            "pending_orders": counts['pending'],
            "shipped_orders": counts['shipped'],
            "delivered_orders": counts['delivered'],
            "inventory": {
                'low_stock_threshold': settings.LOW_STOCK_THRESHOLD,
                **inventory,
            },
            "earnings": {
                key: (float(value) if key != 'paid_order_count' else value)
                for key, value in earnings.items()
            },
            "orders": serializer.data,
            "recent_orders_limit": 10,
        })


# =========================
# UPDATE STATUS
# =========================
class OrderStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def patch(self, request, pk):
        order = get_seller_order(request.user, pk)
        if order is None:
            raise Http404

        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_seller_order_status(order, serializer.validated_data['status'])

        return Response({
            "message": "Order status updated",
            "order_id": order.id,
            "new_status": order.status
        })

class CustomerOrderHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        user = request.user
        orders = get_customer_orders(user)
        paginator = ProductPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        serializer = OrderSerializer(page, many=True)

        return Response({
            "customer": user.email,
            "total_orders": paginator.page.paginator.count,
            "orders": serializer.data,
            "next": paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
        })
