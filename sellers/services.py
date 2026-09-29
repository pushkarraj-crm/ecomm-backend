from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .models import SellerProfile, KYC, BankAccount, Payout
from .selectors import get_seller_earnings_summary, get_seller_profile_for_user


def _get_seller_profile(user):
    seller = get_seller_profile_for_user(user)
    if seller is None:
        raise NotFound('Seller profile not found.')
    return seller


def create_seller_profile(user, business_name):
    return SellerProfile.objects.create(user=user, business_name=business_name)


@transaction.atomic
def create_or_update_kyc(user, pan, aadhaar, document):
    seller = _get_seller_profile(user)

    kyc, _ = KYC.objects.update_or_create(
        seller=seller,
        defaults={
            "pan_card": pan,
            "aadhaar_number": aadhaar,
            "document": document,
        }
    )

    return kyc


@transaction.atomic
def create_or_update_bank(user, account_holder_name, account_number, ifsc_code):
    seller = _get_seller_profile(user)

    bank, _ = BankAccount.objects.update_or_create(
        seller=seller,
        defaults={
            "account_holder_name": account_holder_name,
            "account_number": account_number,
            "ifsc_code": ifsc_code,
        }
    )

    return bank


@transaction.atomic
def request_payout(user, amount):
    seller = _get_seller_profile(user)
    # Serialize payout requests for this seller so concurrent requests cannot
    # both spend the same available balance.
    seller = SellerProfile.objects.select_for_update().get(pk=seller.pk)

    if not seller.is_kyc_verified:
        raise PermissionDenied("KYC not verified")

    if not BankAccount.objects.filter(seller=seller).exists():
        raise ValidationError({'bank_account': 'Add bank details before requesting a payout.'})

    amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise ValidationError({'amount': 'Payout amount must be greater than zero.'})

    available = get_seller_earnings_summary(user)['available_for_payout']
    if amount > available:
        raise ValidationError({
            'amount': (
                f'Requested payout exceeds the available balance of '
                f'₹{available:.2f}.'
            )
        })

    payout = Payout.objects.create(
        seller=seller,
        amount=float(amount),
    )

    return payout
