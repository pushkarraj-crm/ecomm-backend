from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from products.models import ProductInteraction, ProductVariant

from orders.models import Refund, SellerOrder

from .models import Payout, SellerProfile


CENT = Decimal('0.01')


def get_seller_profile_for_user(user):
    return SellerProfile.objects.filter(user=user).first()


def _money(value):
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def _paise_to_money(value):
    return _money(Decimal(value or 0) / Decimal('100'))


def get_seller_earnings_summary(user):
    paid_orders = SellerOrder.objects.filter(
        seller=user,
        order__payment__status='paid',
    )
    sales = paid_orders.aggregate(
        total=Sum('total_amount'),
        count=Count('id'),
    )
    payouts = Payout.objects.filter(seller__user=user).aggregate(
        pending=Sum('amount', filter=Q(status='pending')),
        processed=Sum('amount', filter=Q(status='processed')),
        failed=Sum('amount', filter=Q(status='failed')),
    )
    refunds = Refund.objects.filter(seller_order__seller=user).aggregate(
        pending=Sum('amount_paise', filter=Q(status='pending')),
        processed=Sum('amount_paise', filter=Q(status='processed')),
        failed=Sum('amount_paise', filter=Q(status='failed')),
    )

    gross_paid_sales = _money(sales['total'])
    pending_payouts = _money(payouts['pending'])
    paid_out = _money(payouts['processed'])
    pending_refunds = _paise_to_money(refunds['pending'])
    processed_refunds = _paise_to_money(refunds['processed'])

    return {
        'gross_paid_sales': gross_paid_sales,
        'net_paid_sales': max(gross_paid_sales - processed_refunds, Decimal('0.00')),
        'pending_payouts': pending_payouts,
        'paid_out': paid_out,
        'failed_payouts': _money(payouts['failed']),
        'pending_refunds': pending_refunds,
        'processed_refunds': processed_refunds,
        'failed_refunds': _paise_to_money(refunds['failed']),
        'available_for_payout': max(
            gross_paid_sales - pending_payouts - paid_out - pending_refunds - processed_refunds,
            Decimal('0.00'),
        ),
        'paid_order_count': sales['count'],
    }


def get_recent_seller_earnings(user, limit=10):
    return SellerOrder.objects.filter(
        seller=user,
        order__payment__status='paid',
    ).select_related('order__payment').order_by(
        '-order__payment__updated_at', '-id'
    )[:limit]


def get_seller_payout_history(user, limit=None):
    payouts = Payout.objects.filter(seller__user=user).order_by('-created_at', '-id')
    return payouts if limit is None else payouts[:limit]


def get_seller_inventory(user, stock_status=None, low_stock_threshold=5):
    variants = ProductVariant.objects.filter(product__seller=user).select_related('product')
    if stock_status == 'out_of_stock':
        variants = variants.filter(stock__lte=0)
    elif stock_status == 'low_stock':
        variants = variants.filter(stock__gt=0, stock__lte=low_stock_threshold)
    elif stock_status == 'in_stock':
        variants = variants.filter(stock__gt=0)
    return variants.order_by('product__name', 'size', 'color', 'id')


def get_seller_inventory_summary(user, low_stock_threshold=5):
    return ProductVariant.objects.filter(product__seller=user).aggregate(
        total_variants=Count('id'),
        out_of_stock=Count('id', filter=Q(stock__lte=0)),
        low_stock=Count('id', filter=Q(stock__gt=0, stock__lte=low_stock_threshold)),
        in_stock=Count('id', filter=Q(stock__gt=0)),
    )


def get_seller_business_analytics(user, start_at, end_at, start_date, end_date):
    interactions = ProductInteraction.objects.filter(
        product__seller=user,
        created_at__gte=start_at,
        created_at__lt=end_at,
    )
    interaction_totals = interactions.values('event').annotate(total=Count('id'))
    interaction_counts = {row['event']: row['total'] for row in interaction_totals}
    interaction_by_day = interactions.annotate(
        day=TruncDate('created_at', tzinfo=timezone.get_current_timezone()),
    ).values('day', 'event').annotate(total=Count('id'))

    paid_orders = SellerOrder.objects.filter(seller=user).filter(
        Q(order__payment__isnull=True) | Q(order__payment__status='paid'),
        created_at__gte=start_at,
        created_at__lt=end_at,
    )
    order_totals = paid_orders.aggregate(
        orders=Count('id'),
        sales=Sum('total_amount'),
    )
    orders_by_day = paid_orders.annotate(
        day=TruncDate('created_at', tzinfo=timezone.get_current_timezone()),
    ).values('day').annotate(
        orders=Count('id'),
        sales=Sum('total_amount'),
    )

    processed_returns = Refund.objects.filter(
        seller_order__seller=user,
        seller_order__created_at__gte=start_at,
        seller_order__created_at__lt=end_at,
        status='processed',
    ).aggregate(count=Count('seller_order_id', distinct=True))['count']

    date_count = (end_date - start_date).days + 1
    dates = [start_date + timedelta(days=offset) for offset in range(date_count)]
    views_by_day = {day: 0 for day in dates}
    clicks_by_day = {day: 0 for day in dates}
    for row in interaction_by_day:
        target = views_by_day if row['event'] == 'view' else clicks_by_day
        if row['day'] in target:
            target[row['day']] = row['total']

    orders_count_by_day = {day: 0 for day in dates}
    sales_by_day = {day: 0.0 for day in dates}
    for row in orders_by_day:
        if row['day'] in orders_count_by_day:
            orders_count_by_day[row['day']] = row['orders']
            sales_by_day[row['day']] = round(float(row['sales'] or 0), 2)

    orders_count = order_totals['orders']
    clicks_count = interaction_counts.get('click', 0)
    return {
        'total_views': interaction_counts.get('view', 0),
        'total_clicks': clicks_count,
        'total_orders': orders_count,
        'conversion_rate': round(orders_count / clicks_count * 100, 2) if clicks_count else 0,
        'total_sales': round(float(order_totals['sales'] or 0), 2),
        'return_percentage': round(processed_returns / orders_count * 100, 2) if orders_count else 0,
        'trends': [
            {
                'date': day.isoformat(),
                'views': views_by_day[day],
                'clicks': clicks_by_day[day],
                'orders': orders_count_by_day[day],
                'sales': sales_by_day[day],
            }
            for day in dates
        ],
    }
