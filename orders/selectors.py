from django.db.models import Q

from .models import Order, Payment, SellerOrder


def get_seller_orders(seller, status=None):
    orders = SellerOrder.objects.filter(seller=seller).filter(
        Q(order__payment__isnull=True) | Q(order__payment__status='paid')
    )
    if status:
        orders = orders.filter(status=status)
    return orders.select_related('order', 'order__payment').prefetch_related(
        'items__product_variant__product', 'refunds'
    ).order_by('-id')


def get_seller_order(seller, order_id):
    return SellerOrder.objects.filter(seller=seller, id=order_id).filter(
        Q(order__payment__isnull=True) | Q(order__payment__status='paid')
    ).select_related('order', 'order__payment', 'order__user').prefetch_related(
        'items__product_variant__product', 'refunds'
    ).first()


def get_customer_orders(customer):
    return Order.objects.filter(user=customer).select_related('payment').prefetch_related(
        'seller_orders__items__product_variant__product',
        'seller_orders__refunds',
    ).order_by('-id')


def get_customer_payment(customer, order_id):
    return Payment.objects.filter(order__user=customer, order_id=order_id).select_related(
        'order'
    ).first()


def get_pending_payment_for_customer(customer):
    return Payment.objects.filter(
        order__user=customer,
        status='pending',
        razorpay_order_id__isnull=False,
    ).select_related('order').order_by('-created_at').first()
