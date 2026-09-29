from django.db import transaction

from cart.models import Cart, CartItem
from .models import CustomerAddress, CustomerProfile


@transaction.atomic
def add_to_cart(user, product_variant, quantity):
    cart, _ = Cart.objects.get_or_create(user=user)
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product_variant=product_variant,
        defaults={'quantity': quantity},
    )

    if not created:
        item.quantity += quantity
        item.save(update_fields=['quantity'])

    return cart, item


@transaction.atomic
def save_customer_profile(user, data):
    data = dict(data)
    addresses = data.pop('addresses', None)

    profile, created = CustomerProfile.objects.get_or_create(
        user=user,
        defaults={
            'name': data.get('name', ''),
            'mobile_number': data.get('mobile_number', ''),
        },
    )

    changed_fields = []
    for field in ('name', 'mobile_number'):
        if field in data and getattr(profile, field) != data[field]:
            setattr(profile, field, data[field])
            changed_fields.append(field)

    if changed_fields:
        profile.save(update_fields=changed_fields + ['updated_at'])

    if addresses is not None:
        profile.addresses.all().delete()
        has_default = any(address.get('is_default', False) for address in addresses)
        for index, address_data in enumerate(addresses):
            make_default = address_data.get('is_default', False) or (index == 0 and not has_default)
            create_customer_address(profile, address_data, make_default=make_default)

    return profile, created


@transaction.atomic
def create_customer_address(profile, data, make_default=None):
    data = dict(data)
    requested_default = data.pop('is_default', False)
    is_default = requested_default if make_default is None else make_default

    if is_default or not profile.addresses.exists():
        profile.addresses.update(is_default=False)
        is_default = True

    return CustomerAddress.objects.create(
        profile=profile,
        is_default=is_default,
        **data,
    )


@transaction.atomic
def update_customer_address(address, data):
    data = dict(data)
    is_default = data.pop('is_default', None)

    if is_default is True:
        address.profile.addresses.update(is_default=False)
        address.is_default = True

    for field, value in data.items():
        setattr(address, field, value)

    if is_default is False:
        address.is_default = False

    address.save()
    return address


@transaction.atomic
def delete_customer_address(address):
    profile = address.profile
    was_default = address.is_default
    address.delete()

    if was_default:
        replacement = profile.addresses.order_by('id').first()
        if replacement:
            replacement.is_default = True
            replacement.save(update_fields=['is_default'])
