from django.conf import settings
from datetime import date, datetime, time, timedelta
from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsApprovedSeller, IsSeller
from orders.invoices import generate_seller_invoice
from orders.models import SellerOrder
from orders.selectors import get_seller_order
from orders.services import request_seller_order_refund
from .services import create_or_update_kyc, create_or_update_bank, request_payout
from .serializers import (
    BankDetailsInputSerializer,
    InventoryStockUpdateSerializer,
    KYCSubmissionSerializer,
    PayoutRequestSerializer,
    SellerInventoryVariantSerializer,
    SellerEarningSerializer,
    SellerPayoutHistorySerializer,
    SellerRefundRequestSerializer,
    SellerRefundSerializer,
)
from .selectors import (
    get_seller_business_analytics,
    get_seller_inventory,
    get_seller_inventory_summary,
    get_recent_seller_earnings,
    get_seller_earnings_summary,
    get_seller_payout_history,
    get_seller_profile_for_user,
)
from orders.selectors import get_seller_orders
from orders.serializers import SellerOrderSerializer
from core.pagination import ProductPagination
from orders.gateways.razorpay import RazorpayGatewayError
from products.models import ProductVariant
from products.bulk_catalog import create_bulk_catalog_template, import_bulk_catalog


class SellerOrderListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        order_status = request.query_params.get('status')
        allowed_statuses = {choice[0] for choice in SellerOrder.STATUS_CHOICES}
        if order_status and order_status not in allowed_statuses:
            raise ValidationError({
                'status': f"Choose one of: {', '.join(sorted(allowed_statuses))}."
            })
        orders = get_seller_orders(request.user, status=order_status)
        paginator = ProductPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        serializer = SellerOrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class SellerInventorySummaryAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        return Response({
            'low_stock_threshold': settings.LOW_STOCK_THRESHOLD,
            **get_seller_inventory_summary(
                request.user,
                low_stock_threshold=settings.LOW_STOCK_THRESHOLD,
            ),
        })


class SellerInventoryAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        stock_status = request.query_params.get('status')
        allowed_statuses = {'out_of_stock', 'low_stock', 'in_stock'}
        if stock_status and stock_status not in allowed_statuses:
            raise ValidationError({
                'status': f"Choose one of: {', '.join(sorted(allowed_statuses))}."
            })

        variants = get_seller_inventory(
            request.user,
            stock_status=stock_status,
            low_stock_threshold=settings.LOW_STOCK_THRESHOLD,
        )
        paginator = ProductPagination()
        page = paginator.paginate_queryset(variants, request, view=self)
        serializer = SellerInventoryVariantSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class SellerInventoryStockAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def patch(self, request, variant_id):
        serializer = InventoryStockUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        variant = ProductVariant.objects.filter(
            id=variant_id,
            product__seller=request.user,
        ).first()
        if variant is None:
            raise Http404

        variant.stock = serializer.validated_data['stock']
        variant.save(update_fields=['stock'])
        return Response(SellerInventoryVariantSerializer(variant).data)


class SellerOrderInvoiceAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request, pk):
        seller_order = get_seller_order(request.user, pk)
        if seller_order is None:
            raise Http404

        seller_profile = get_seller_profile_for_user(request.user)
        pdf = generate_seller_invoice(seller_order, seller_profile=seller_profile)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice-D2C-SO-{seller_order.id}.pdf"'
        response['Cache-Control'] = 'private, no-store'
        return response


class SellerOrderRefundAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request, pk):
        seller_order = get_seller_order(request.user, pk)
        if seller_order is None:
            raise Http404
        refunds = seller_order.refunds.order_by('-created_at', '-id')
        paginator = ProductPagination()
        page = paginator.paginate_queryset(refunds, request, view=self)
        response = paginator.get_paginated_response(SellerRefundSerializer(page, many=True).data)
        response.data['seller_order_id'] = seller_order.id
        return response

    def post(self, request, pk):
        seller_order = get_seller_order(request.user, pk)
        if seller_order is None:
            raise Http404

        serializer = SellerRefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refund, created = request_seller_order_refund(
                seller_order=seller_order,
                requested_by=request.user,
                amount=serializer.validated_data['amount'],
                reason=serializer.validated_data['reason'],
                idempotency_key=serializer.validated_data['idempotency_key'],
            )
        except RazorpayGatewayError as error:
            return Response({'error': str(error)}, status=error.status_code)

        return Response({
            'message': 'Refund request submitted.' if created else 'Existing refund request returned.',
            'refund': SellerRefundSerializer(refund).data,
        }, status=201 if created else 200)


class KYCAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request):
        serializer = KYCSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        create_or_update_kyc(
            request.user,
            pan=serializer.validated_data['pan'],
            aadhaar=serializer.validated_data['aadhaar'],
            document=serializer.validated_data['document'],
        )
        return Response({"message": "KYC submitted"})


class BankAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request):
        serializer = BankDetailsInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        create_or_update_bank(
            request.user,
            account_holder_name=serializer.validated_data['name'],
            account_number=serializer.validated_data['account'],
            ifsc_code=serializer.validated_data['ifsc'],
        )
        return Response({"message": "Bank details saved"})


class PayoutAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        payouts = get_seller_payout_history(request.user)
        paginator = ProductPagination()
        page = paginator.paginate_queryset(payouts, request, view=self)
        return paginator.get_paginated_response(SellerPayoutHistorySerializer(page, many=True).data)

    def post(self, request):
        serializer = PayoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payout = request_payout(request.user, serializer.validated_data['amount'])
        return Response({
            "message": "Payout requested",
            "payout": SellerPayoutHistorySerializer(payout).data,
        })


class SellerEarningsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        summary = get_seller_earnings_summary(request.user)
        recent_sales = get_recent_seller_earnings(request.user)
        recent_payouts = get_seller_payout_history(request.user, limit=10)

        return Response({
            'seller': request.user.email,
            'currency': 'INR',
            'summary': {
                key: (float(value) if key != 'paid_order_count' else value)
                for key, value in summary.items()
            },
            'recent_sales': SellerEarningSerializer(recent_sales, many=True).data,
            'recent_payouts': SellerPayoutHistorySerializer(recent_payouts, many=True).data,
        })


class SellerBusinessAnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        period = request.query_params.get('period', 'last_7_days').strip().lower()
        today = timezone.localdate()
        if period == 'yesterday':
            start_date = end_date = today - timedelta(days=1)
        elif period == 'last_7_days':
            start_date, end_date = today - timedelta(days=6), today
        elif period == 'last_30_days':
            start_date, end_date = today - timedelta(days=29), today
        elif period == 'custom':
            try:
                start_date = date.fromisoformat(request.query_params['start_date'])
                end_date = date.fromisoformat(request.query_params['end_date'])
            except (KeyError, TypeError, ValueError):
                raise ValidationError({
                    'date_range': 'For custom periods, provide start_date and end_date as YYYY-MM-DD.',
                })
        else:
            raise ValidationError({
                'period': 'Choose yesterday, last_7_days, last_30_days, or custom.',
            })

        if start_date > end_date:
            raise ValidationError({'date_range': 'start_date must be on or before end_date.'})
        if end_date == date.max:
            raise ValidationError({'date_range': 'end_date must be before 9999-12-31.'})
        if (end_date - start_date).days >= 366:
            raise ValidationError({'date_range': 'Date range cannot exceed 366 days.'})

        current_tz = timezone.get_current_timezone()
        start_at = timezone.make_aware(datetime.combine(start_date, time.min), current_tz)
        end_at = timezone.make_aware(
            datetime.combine(end_date + timedelta(days=1), time.min),
            current_tz,
        )
        analytics = get_seller_business_analytics(
            request.user,
            start_at=start_at,
            end_at=end_at,
            start_date=start_date,
            end_date=end_date,
        )
        return Response({
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'currency': 'INR',
            **analytics,
        })


class SellerBulkCatalogTemplateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedSeller]

    def get(self, request):
        return create_bulk_catalog_template()


class SellerBulkCatalogAPIView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedSeller]

    def post(self, request):
        upload = request.FILES.get('file')
        if upload is None:
            raise ValidationError({'file': 'Attach an .xlsx file using the file field.'})
        products, variant_count = import_bulk_catalog(request.user, upload)
        return Response({
            'message': 'Catalog uploaded. Products are pending review.',
            'product_count': len(products),
            'variant_count': variant_count,
            'products': [
                {'id': product.id, 'name': product.name, 'status': product.status}
                for product in products
            ],
        }, status=201)
