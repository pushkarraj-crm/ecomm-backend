from decimal import Decimal, ROUND_HALF_UP
import random
import unicodedata

from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from django.utils import timezone

from .models import SellerProfile, KYC, BankAccount, Payout
from .razorpayx import RazorpayXError, RazorpayXGateway
from .selectors import get_seller_earnings_summary, get_seller_profile_for_user


def _get_seller_profile(user):
    seller = get_seller_profile_for_user(user)
    if seller is None:
        raise NotFound("Seller profile not found.")
    return seller


def create_seller_profile(user, business_name, **profile_fields):
    profile_fields.setdefault("store_name", business_name)
    profile_fields.setdefault(
        "gst_verification_status",
        "pending" if profile_fields.get("gst_registered") else "not_required",
    )
    return SellerProfile.objects.create(
        user=user,
        business_name=business_name,
        **profile_fields,
    )


@transaction.atomic
def create_or_update_kyc(user, pan, aadhaar, document):
    seller = _get_seller_profile(user)

    kyc, _ = KYC.objects.update_or_create(
        seller=seller,
        defaults={
            "pan_card": pan,
            "aadhaar_number": aadhaar,
            "document": document,
        },
    )

    return kyc


@transaction.atomic
def create_or_update_bank(user, account_holder_name, account_number, ifsc_code):
    seller = _get_seller_profile(user)
    bank = BankAccount.objects.select_for_update().filter(seller=seller).first()
    same_details = bank and (
        bank.account_holder_name == account_holder_name
        and bank.account_number == account_number
        and bank.ifsc_code == ifsc_code
    )
    if same_details:
        return bank
    if bank and bank.verification_status in {"processing", "amount_confirmation"}:
        raise ValidationError(
            {
                "bank": "Complete or fail the current verification before changing bank details."
            }
        )

    if bank is None:
        bank = BankAccount(seller=seller)
    bank.account_holder_name = account_holder_name
    bank.account_number = account_number
    bank.ifsc_code = ifsc_code
    bank.verification_status = "pending"
    bank.verified_account_name = ""
    bank.verification_reference = ""
    bank.razorpay_contact_id = ""
    bank.razorpay_fund_account_id = ""
    bank.validation_amount_paise = None
    bank.verification_attempts = 0
    bank.verified_at = None
    bank.save()
    return bank


def _normalize_person_name(value):
    normalized = unicodedata.normalize("NFKD", value or "").casefold()
    return "".join(character for character in normalized if character.isalnum())


def _expected_bank_name(seller):
    if seller.gst_registered:
        if seller.gst_verification_status != "verified" or not seller.gst_legal_name:
            raise ValidationError(
                {"gst": "Verify GST before verifying the seller bank account."}
            )
        return seller.gst_legal_name
    if not seller.owner_full_name:
        raise ValidationError(
            {
                "owner_full_name": "Add the owner full name before verifying the bank account."
            }
        )
    return seller.owner_full_name


def start_bank_verification(user):
    seller = _get_seller_profile(user)
    expected_name = _expected_bank_name(seller)
    bank = BankAccount.objects.filter(seller=seller).first()
    if bank is None:
        raise NotFound("Save bank details before starting verification.")
    if _normalize_person_name(bank.account_holder_name) != _normalize_person_name(
        expected_name
    ):
        raise ValidationError(
            {
                "name": "Bank account holder name must match the verified GST legal name or owner full name."
            }
        )
    if bank.verification_status == "verified":
        return bank
    if bank.verification_status in {"processing", "amount_confirmation"}:
        return bank
    if bank.verification_status == "failed" and bank.verification_reference:
        raise ValidationError(
            {
                "bank": "This account has already had a verification attempt. Submit different bank details or contact support."
            }
        )
    gateway = RazorpayXGateway()

    with transaction.atomic():
        bank = BankAccount.objects.select_for_update().get(pk=bank.pk)
        if bank.verification_status in {
            "processing",
            "amount_confirmation",
            "verified",
        }:
            return bank
        if bank.verification_status == "failed" and bank.verification_reference:
            raise ValidationError(
                {
                    "bank": "This account has already had a verification attempt. Submit different bank details or contact support."
                }
            )
        bank.verification_status = "processing"
        bank.verified_account_name = ""
        bank.save(update_fields=["verification_status", "verified_account_name"])

    try:
        name = (
            seller.owner_full_name or seller.gst_legal_name or seller.store_name
        ).strip()
        contact = gateway.create_contact(
            name=name,
            email=user.email,
            reference_id=f"seller-{seller.pk}",
        )
        contact_id = contact.get("id")
        if not contact_id:
            raise RazorpayXError("RazorpayX did not return a contact reference.")
        bank.razorpay_contact_id = contact_id
        bank.save(update_fields=["razorpay_contact_id"])

        fund_account = gateway.create_bank_fund_account(
            contact_id=contact_id,
            name=bank.account_holder_name,
            ifsc=bank.ifsc_code,
            account_number=bank.account_number,
        )
        fund_account_id = fund_account.get("id")
        if not fund_account_id:
            raise RazorpayXError("RazorpayX did not return a fund account reference.")
        bank.razorpay_fund_account_id = fund_account_id
        bank.save(update_fields=["razorpay_fund_account_id"])

        amount_paise = random.SystemRandom().randint(100, 200)
        validation = gateway.create_account_validation(
            fund_account_id=fund_account_id,
            amount_paise=amount_paise,
            seller_id=seller.pk,
        )
        validation_id = validation.get("id")
        if not validation_id:
            raise RazorpayXError("RazorpayX did not return a validation reference.")
        bank.verification_reference = validation_id
        bank.validation_amount_paise = amount_paise
        bank.verification_status = "processing"
        bank.save(
            update_fields=[
                "verification_reference",
                "validation_amount_paise",
                "verification_status",
            ]
        )
        if validation.get("status") in {"completed", "failed"}:
            return _apply_bank_validation_result(bank, validation, expected_name)
        return bank
    except (RazorpayXError, OSError) as error:
        bank.refresh_from_db()
        # A timeout or provider 5xx may happen after the transfer was created.
        # Keep it pending so a retry cannot accidentally create a second transfer.
        status_code = getattr(error, "status_code", 502)
        if status_code < 500 and not bank.verification_reference:
            bank.verification_status = "failed"
            bank.save(update_fields=["verification_status"])
        raise


def _apply_bank_validation_result(bank, validation, expected_name):
    status = validation.get("status")
    if status == "failed":
        bank.verification_status = "failed"
    elif status == "completed":
        results = validation.get("results") or {}
        registered_name = (results.get("registered_name") or "").strip()
        account_status = results.get("account_status")
        bank.verified_account_name = registered_name
        if (
            account_status == "active"
            and registered_name
            and _normalize_person_name(registered_name)
            == _normalize_person_name(expected_name)
        ):
            bank.verification_status = "amount_confirmation"
        else:
            bank.verification_status = "failed"
    else:
        bank.verification_status = "processing"
    bank.save(update_fields=["verification_status", "verified_account_name"])
    return bank


def refresh_bank_verification(user):
    seller = _get_seller_profile(user)
    expected_name = _expected_bank_name(seller)
    bank = BankAccount.objects.filter(seller=seller).first()
    if bank is None:
        raise NotFound("Bank details not found.")
    if bank.verification_status in {"verified", "failed", "pending"}:
        return bank
    if not bank.verification_reference:
        return bank
    validation = RazorpayXGateway().fetch_account_validation(
        bank.verification_reference
    )
    return _apply_bank_validation_result(bank, validation, expected_name)


def confirm_bank_verification_amount(user, amount):
    seller = _get_seller_profile(user)
    with transaction.atomic():
        bank = BankAccount.objects.select_for_update().filter(seller=seller).first()
        if bank is None:
            raise NotFound("Bank details not found.")
        if (
            bank.verification_status != "amount_confirmation"
            or bank.validation_amount_paise is None
        ):
            raise ValidationError(
                {
                    "bank": "The bank verification transfer is not ready for amount confirmation."
                }
            )
        submitted_amount_paise = int(Decimal(str(amount)) * Decimal("100"))
        if submitted_amount_paise != bank.validation_amount_paise:
            bank.verification_attempts += 1
            if bank.verification_attempts >= 3:
                bank.verification_status = "failed"
                bank.validation_amount_paise = None
            bank.save(
                update_fields=[
                    "verification_attempts",
                    "verification_status",
                    "validation_amount_paise",
                ]
            )
            return bank, False

        bank.verification_status = "verified"
        bank.verified_at = timezone.now()
        bank.validation_amount_paise = None
        bank.verification_attempts = 0
        bank.save(
            update_fields=[
                "verification_status",
                "verified_at",
                "validation_amount_paise",
                "verification_attempts",
            ]
        )
        return bank, True


@transaction.atomic
def request_payout(user, amount):
    seller = _get_seller_profile(user)
    # Serialize payout requests for this seller so concurrent requests cannot
    # both spend the same available balance.
    seller = SellerProfile.objects.select_for_update().get(pk=seller.pk)

    if not seller.is_kyc_verified:
        raise PermissionDenied("KYC not verified")

    bank = BankAccount.objects.filter(seller=seller).first()
    if bank is None:
        raise ValidationError(
            {"bank_account": "Add bank details before requesting a payout."}
        )
    if bank.verification_status != "verified":
        raise ValidationError(
            {"bank_account": "Verify the bank account before requesting a payout."}
        )
    expected_name = _expected_bank_name(seller)
    if _normalize_person_name(bank.verified_account_name) != _normalize_person_name(
        expected_name
    ):
        raise ValidationError(
            {
                "bank_account": "Verified bank name no longer matches the seller legal name."
            }
        )

    amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise ValidationError({"amount": "Payout amount must be greater than zero."})

    available = get_seller_earnings_summary(user)["available_for_payout"]
    if amount > available:
        raise ValidationError(
            {
                "amount": (
                    f"Requested payout exceeds the available balance of "
                    f"₹{available:.2f}."
                )
            }
        )

    payout = Payout.objects.create(
        seller=seller,
        amount=float(amount),
    )

    return payout
