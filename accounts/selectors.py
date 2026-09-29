from .models import User


def get_user_by_email(email):
    return User.objects.filter(email=email).first()


def get_active_user_by_email(email):
    return User.objects.filter(email=email, is_active=True).first()


def get_active_user_by_id(user_id):
    return User.objects.filter(pk=user_id, is_active=True).first()


def get_approved_sellers():
    return User.objects.filter(is_seller=True, seller_status='approved')
