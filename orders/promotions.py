"""Server-side seller-funded discounts shared by preview and checkout."""
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Coupon


def price_cart(items, code=''):
    code = code.strip().upper()
    coupon = None
    if code:
        coupon = Coupon.objects.filter(code=code, is_active=True, starts_at__lte=timezone.now(), expires_at__gt=timezone.now()).first()
        if not coupon:
            raise ValidationError({'coupon_code': 'Coupon is invalid, inactive or expired.'})
    prices = {}
    subtotal = total = eligible = 0
    for item in items:
        base = int((Decimal(str(item.product_variant.price))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        applicable = coupon and item.product_variant.product.seller_id == coupon.seller_id
        if applicable:
            eligible += base * item.quantity
        net = max(1, int((Decimal(base)*Decimal(100-coupon.percent)/100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))) if applicable else base
        prices[item.pk] = net
        subtotal += base * item.quantity
        total += net * item.quantity
    if coupon and (eligible == 0 or Decimal(eligible)/100 < coupon.minimum_subtotal):
        raise ValidationError({'coupon_code': 'This seller’s eligible items do not meet the coupon minimum.'})
    return {'prices': prices, 'subtotal_paise': subtotal, 'total_paise': total, 'discount_paise': subtotal-total, 'coupon_code': code}
