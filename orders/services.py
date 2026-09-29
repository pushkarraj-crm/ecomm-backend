from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.db.models import F, Sum
from rest_framework.exceptions import ValidationError

from cart.models import Cart, CartItem
from cart.selectors import get_cart_for_user
from customers.models import CustomerAddress
from products.models import ProductVariant
from .gateways.razorpay import RazorpayGateway, RazorpayGatewayError
from .models import Order, Payment, Refund, SellerOrder, OrderItem
from .selectors import get_pending_payment_for_customer


class PaymentVerificationError(Exception):
    status_code = 400


class PaymentStateConflict(PaymentVerificationError):
    status_code = 409


def amount_to_paise(amount):
    return int(
        (Decimal(str(amount)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    )


@transaction.atomic
def create_order_from_cart(user, data):
    cart = get_cart_for_user(user)
    if cart is None:
        raise ValidationError({'cart': 'Your cart is empty.'})

    items = list(cart.items.select_related('product_variant__product'))
    if not items:
        raise ValidationError({'cart': 'Your cart is empty.'})
    if any(
        item.quantity < 1 or amount_to_paise(item.product_variant.price) < 1
        for item in items
    ):
        raise ValidationError({
            'cart': 'Every cart item must have a positive quantity and a price of at least ₹0.01.'
        })
    for item in items:
        if item.quantity > item.product_variant.stock:
            raise ValidationError({
                'stock': (
                    f'Not enough stock for {item.product_variant.product.name} '
                    f'({item.product_variant.size}, {item.product_variant.color}). '
                    f'Available quantity: {max(item.product_variant.stock, 0)}.'
                )
            })

    delivery_address = {'address': data.get('address', '')}
    if 'address_id' in data:
        try:
            saved_address = CustomerAddress.objects.get(
                pk=data['address_id'],
                profile__user=user,
            )
        except CustomerAddress.DoesNotExist:
            raise ValidationError({'address_id': 'Select one of your saved addresses.'})

        required_fields = ('address_line_1', 'city', 'state', 'postal_code')
        missing_fields = [
            field for field in required_fields if not getattr(saved_address, field)
        ]
        if missing_fields:
            raise ValidationError({
                'address_id': (
                    'The selected address is not ready for delivery. Add '
                    'address_line_1, city, state, and postal_code to it.'
                )
            })

        delivery_address = {
            field: getattr(saved_address, field)
            for field in (
                'address', 'address_line_1', 'address_line_2', 'landmark',
                'city', 'state', 'postal_code', 'country',
            )
        }

    order = Order.objects.create(
        user=user,
        name=data['name'],
        phone=data['phone'],
        email=user.email,
        **delivery_address,
        total_amount=0
    )

    seller_map = defaultdict(list)

    for item in items:
        seller = item.product_variant.product.seller
        seller_map[seller].append(item)

    total_order_paise = 0

    for seller, seller_items in seller_map.items():
        seller_total_paise = 0

        seller_order = SellerOrder.objects.create(
            order=order,
            seller=seller,
            total_amount=0
        )

        for item in seller_items:
            price_paise = amount_to_paise(item.product_variant.price)
            price = price_paise / 100

            OrderItem.objects.create(
                seller_order=seller_order,
                product_variant=item.product_variant,
                quantity=item.quantity,
                price=price
            )

            seller_total_paise += price_paise * item.quantity

        seller_order.total_amount = seller_total_paise / 100
        seller_order.save()

        total_order_paise += seller_total_paise

    order.total_amount = total_order_paise / 100
    order.save()

    return order


def create_razorpay_payment(user, checkout_data):
    gateway = RazorpayGateway()
    pending_payment = get_pending_payment_for_customer(user)
    if pending_payment:
        return pending_payment.order, pending_payment

    order = create_order_from_cart(user, checkout_data)
    amount_paise = amount_to_paise(order.total_amount)
    if amount_paise <= 0:
        raise ValidationError({'cart': 'The order total must be greater than zero.'})

    currency = 'INR'
    payment = Payment.objects.create(
        order=order,
        amount_paise=amount_paise,
        currency=currency,
    )

    try:
        razorpay_order = gateway.create_order(
            amount_paise=amount_paise,
            currency=currency,
            receipt=f'order_{order.id}',
        )
        if (
            not razorpay_order.get('id')
            or razorpay_order.get('amount') != amount_paise
            or razorpay_order.get('currency') != currency
        ):
            raise RazorpayGatewayError('Razorpay returned an invalid order response.')
    except RazorpayGatewayError:
        payment.status = 'failed'
        payment.save(update_fields=['status', 'updated_at'])
        order.status = 'failed'
        order.save(update_fields=['status'])
        raise

    payment.razorpay_order_id = razorpay_order['id']
    payment.save(update_fields=['razorpay_order_id', 'updated_at'])
    return order, payment


def _remove_paid_items_from_cart(order):
    cart = Cart.objects.filter(user=order.user).first()
    if cart is None:
        return

    ordered_items = OrderItem.objects.filter(seller_order__order=order)
    for ordered_item in ordered_items:
        cart_item = CartItem.objects.filter(
            cart=cart,
            product_variant_id=ordered_item.product_variant_id,
        ).select_for_update().first()
        if cart_item is None:
            continue

        remaining_quantity = cart_item.quantity - ordered_item.quantity
        if remaining_quantity <= 0:
            cart_item.delete()
        else:
            cart_item.quantity = remaining_quantity
            cart_item.save(update_fields=['quantity'])


@transaction.atomic
def _mark_payment_paid(payment_id, razorpay_payment_id):
    payment = Payment.objects.select_for_update().select_related('order').get(pk=payment_id)
    if payment.status == 'paid':
        if payment.razorpay_payment_id == razorpay_payment_id:
            return payment.order
        raise PaymentStateConflict('This order has already been paid.')
    if payment.status != 'pending':
        raise PaymentStateConflict('This payment is no longer pending.')

    payment.status = 'paid'
    payment.razorpay_payment_id = razorpay_payment_id
    payment.save(update_fields=['status', 'razorpay_payment_id', 'updated_at'])
    payment.order.status = 'paid'
    payment.order.save(update_fields=['status'])
    for ordered_item in OrderItem.objects.filter(seller_order__order=payment.order):
        ProductVariant.objects.filter(pk=ordered_item.product_variant_id).update(
            stock=F('stock') - ordered_item.quantity,
        )
    _remove_paid_items_from_cart(payment.order)
    return payment.order


def verify_razorpay_payment(payment, razorpay_order_id, razorpay_payment_id, signature):
    if payment.status == 'paid':
        if payment.razorpay_payment_id == razorpay_payment_id:
            return payment.order
        raise PaymentStateConflict('This order has already been paid.')
    if payment.status != 'pending' or not payment.razorpay_order_id:
        raise PaymentStateConflict('This payment is no longer pending.')
    if razorpay_order_id != payment.razorpay_order_id:
        raise PaymentVerificationError('The Razorpay order does not match this checkout.')

    gateway = RazorpayGateway()
    if not gateway.verify_payment_signature(
        order_id=payment.razorpay_order_id,
        payment_id=razorpay_payment_id,
        signature=signature,
    ):
        raise PaymentVerificationError('Razorpay payment signature is invalid.')

    payment_details = gateway.fetch_payment(razorpay_payment_id)
    if (
        payment_details.get('order_id') != payment.razorpay_order_id
        or payment_details.get('amount') != payment.amount_paise
        or payment_details.get('currency') != payment.currency
    ):
        raise PaymentVerificationError('The Razorpay payment details do not match this order.')
    if payment_details.get('status') != 'captured':
        raise PaymentStateConflict('Razorpay has not captured this payment yet.')

    return _mark_payment_paid(payment.id, razorpay_payment_id)


def _refund_amounts(queryset):
    return queryset.filter(status__in=('pending', 'processed')).aggregate(
        total=Sum('amount_paise')
    )['total'] or 0


def _set_order_refund_status(payment):
    refunded_paise = Refund.objects.filter(
        payment=payment,
        status='processed',
    ).aggregate(total=Sum('amount_paise'))['total'] or 0
    if refunded_paise >= payment.amount_paise:
        new_status = 'refunded'
    elif refunded_paise > 0:
        new_status = 'partially_refunded'
    else:
        new_status = 'paid'
    if payment.order.status != new_status:
        payment.order.status = new_status
        payment.order.save(update_fields=['status'])


def request_seller_order_refund(seller_order, requested_by, amount, reason, idempotency_key):
    amount_paise = amount_to_paise(amount)
    if amount_paise < 1:
        raise ValidationError({'amount': 'Refund must be at least INR 0.01.'})

    with transaction.atomic():
        # Use the same seller-profile lock as payout requests to keep balance
        # reservations serialized across refunds and payouts.
        from sellers.models import SellerProfile

        seller_profile = SellerProfile.objects.select_for_update().filter(
            user=requested_by
        ).first()
        if seller_profile is None:
            raise ValidationError({'seller': 'Seller profile not found.'})

        locked_seller_order = SellerOrder.objects.select_for_update().select_related(
            'order'
        ).get(pk=seller_order.pk, seller=requested_by)

        existing = Refund.objects.filter(
            requested_by=requested_by,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            if (
                existing.seller_order_id != locked_seller_order.id
                or existing.amount_paise != amount_paise
                or existing.reason != reason
            ):
                raise ValidationError({
                    'idempotency_key': 'This key was already used for a different refund request.'
                })
            return existing, False

        try:
            payment = Payment.objects.select_for_update().select_related('order').get(
                order_id=locked_seller_order.order_id
            )
        except Payment.DoesNotExist:
            raise ValidationError({'order': 'This order has no refundable payment.'})

        if payment.status != 'paid' or not payment.razorpay_payment_id:
            raise ValidationError({'order': 'Only paid Razorpay orders can be refunded.'})

        seller_reserved = _refund_amounts(
            Refund.objects.filter(seller_order=locked_seller_order)
        )
        seller_order_limit = amount_to_paise(locked_seller_order.total_amount)
        if seller_reserved + amount_paise > seller_order_limit:
            remaining = max(seller_order_limit - seller_reserved, 0)
            raise ValidationError({
                'amount': f'Refund exceeds this seller order’s remaining refundable balance of INR {remaining / 100:.2f}.'
            })

        payment_reserved = _refund_amounts(Refund.objects.filter(payment=payment))
        if payment_reserved + amount_paise > payment.amount_paise:
            remaining = max(payment.amount_paise - payment_reserved, 0)
            raise ValidationError({
                'amount': f'Refund exceeds the payment’s remaining refundable balance of INR {remaining / 100:.2f}.'
            })

        refund = Refund.objects.create(
            seller_order=locked_seller_order,
            payment=payment,
            requested_by=requested_by,
            idempotency_key=idempotency_key,
            amount_paise=amount_paise,
            reason=reason,
            status='pending',
        )

    # The pending row is committed before the network request, so it reserves
    # the balance and can safely be reconciled if the provider times out.
    try:
        gateway = RazorpayGateway()
        response = gateway.create_refund(
            payment_id=payment.razorpay_payment_id,
            amount_paise=amount_paise,
            notes={
                'seller_order_id': str(locked_seller_order.id),
                'local_refund_id': str(refund.id),
            },
        )
    except RazorpayGatewayError as error:
        if error.definitive:
            update_refund_status(
                refund.id,
                status='failed',
                failure_reason='Razorpay rejected the refund request.',
            )
        raise

    if (
        not response.get('id')
        or response.get('payment_id') != payment.razorpay_payment_id
        or response.get('amount') != amount_paise
    ):
        raise RazorpayGatewayError('Razorpay returned an invalid refund response.')

    response_status = response.get('status', 'pending')
    if response_status not in {'pending', 'processed', 'failed'}:
        response_status = 'pending'
    refund.razorpay_refund_id = response['id']
    refund.status = response_status
    if response_status == 'failed':
        refund.failure_reason = 'Razorpay marked the refund as failed.'
    refund.save(update_fields=[
        'razorpay_refund_id', 'status', 'failure_reason', 'updated_at'
    ])
    if response_status in {'processed', 'failed'}:
        update_refund_status(
            refund.id,
            status=response_status,
            failure_reason=refund.failure_reason,
        )
    return refund, True


@transaction.atomic
def update_refund_status(refund_id, status, failure_reason=''):
    refund = Refund.objects.select_for_update().select_related(
        'payment__order'
    ).filter(pk=refund_id).first()
    if refund is None or status not in {'pending', 'processed', 'failed'}:
        return refund
    if refund.status in {'processed', 'failed'}:
        _set_order_refund_status(refund.payment)
        return refund

    refund.status = status
    if status == 'failed':
        refund.failure_reason = failure_reason[:255]
    refund.save(update_fields=['status', 'failure_reason', 'updated_at'])
    _set_order_refund_status(refund.payment)
    return refund


@transaction.atomic
def update_refund_status_by_gateway_id(razorpay_refund_id, status, failure_reason=''):
    refund = Refund.objects.filter(razorpay_refund_id=razorpay_refund_id).first()
    if refund is None:
        return None
    return update_refund_status(refund.id, status, failure_reason)


@transaction.atomic
def update_seller_order_status(order, new_status):
    order.status = new_status
    order.save(update_fields=['status'])
    return order
