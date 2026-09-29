from .models import Cart, CartItem


def get_cart_for_user(user):
    return Cart.objects.filter(user=user).prefetch_related(
        'items__product_variant__product'
    ).first()


def get_cart_item_for_user(user, item_id):
    return CartItem.objects.filter(id=item_id, cart__user=user).first()
