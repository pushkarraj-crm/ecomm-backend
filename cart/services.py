from django.db import transaction

from .models import Cart, CartItem


@transaction.atomic
def get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@transaction.atomic
def update_cart_item(item, quantity):
    item.quantity = quantity
    item.save(update_fields=['quantity'])
    return item


@transaction.atomic
def remove_cart_item(item):
    item.delete()


@transaction.atomic
def clear_cart(cart):
    cart.items.all().delete()
