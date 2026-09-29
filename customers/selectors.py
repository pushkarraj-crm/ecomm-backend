from .models import CustomerAddress, CustomerProfile


def get_customer_profile(user):
    return CustomerProfile.objects.filter(user=user).prefetch_related('addresses').first()


def get_customer_address(user, address_id):
    return CustomerAddress.objects.filter(
        id=address_id,
        profile__user=user,
    ).select_related('profile').first()
