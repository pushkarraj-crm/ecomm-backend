from django.db import models
from django.conf import settings


class SellerProfile(models.Model):
    BUSINESS_TYPE_CHOICES = (
        ("individual", "Individual"),
        ("sole_proprietorship", "Sole proprietorship"),
        ("partnership", "Partnership"),
        ("llp", "Limited liability partnership"),
        ("private_limited", "Private limited company"),
        ("public_limited", "Public limited company"),
        ("other", "Other"),
    )
    GST_STATUS_CHOICES = (
        ("not_required", "Not required"),
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("failed", "Failed"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile",
    )

    business_name = models.CharField(max_length=255)
    store_name = models.CharField(max_length=255, blank=True)
    owner_full_name = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(
        max_length=32, choices=BUSINESS_TYPE_CHOICES, blank=True
    )
    gst_registered = models.BooleanField(default=False)
    gst_number = models.CharField(max_length=50, blank=True, null=True)
    gst_legal_name = models.CharField(max_length=255, blank=True)
    gst_registered_address = models.JSONField(default=dict, blank=True)
    gst_verification_status = models.CharField(
        max_length=16,
        choices=GST_STATUS_CHOICES,
        default="not_required",
    )
    gst_verified_at = models.DateTimeField(null=True, blank=True)
    use_gst_registered_address = models.BooleanField(default=False)
    pickup_address_line_1 = models.CharField(max_length=255, blank=True)
    pickup_address_line_2 = models.CharField(max_length=255, blank=True)
    pickup_landmark = models.CharField(max_length=255, blank=True)
    pickup_city = models.CharField(max_length=100, blank=True)
    pickup_state = models.CharField(max_length=100, blank=True)
    pickup_postal_code = models.CharField(max_length=20, blank=True)
    pickup_country = models.CharField(max_length=100, default="India")

    is_kyc_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.business_name


class KYC(models.Model):
    seller = models.OneToOneField(SellerProfile, on_delete=models.CASCADE)

    pan_card = models.CharField(max_length=20)
    aadhaar_number = models.CharField(max_length=20)
    document = models.FileField(upload_to="kyc/")

    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )


class BankAccount(models.Model):
    VERIFICATION_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("amount_confirmation", "Amount confirmation"),
        ("verified", "Verified"),
        ("failed", "Failed"),
    )

    seller = models.OneToOneField(SellerProfile, on_delete=models.CASCADE)

    account_holder_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default="pending",
    )
    verified_account_name = models.CharField(max_length=255, blank=True)
    verification_reference = models.CharField(max_length=128, blank=True)
    razorpay_contact_id = models.CharField(max_length=64, blank=True)
    razorpay_fund_account_id = models.CharField(max_length=64, blank=True)
    validation_amount_paise = models.PositiveSmallIntegerField(null=True, blank=True)
    verification_attempts = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)


class Payout(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE)

    amount = models.FloatField()

    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("processed", "Processed"),
            ("failed", "Failed"),
        ],
        default="pending",
    )

    created_at = models.DateTimeField(auto_now_add=True)


class SellerCatalogSubmission(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
