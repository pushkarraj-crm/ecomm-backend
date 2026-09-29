from django.db import models
from django.conf import settings


class SellerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_profile'
    )

    business_name = models.CharField(max_length=255)
    gst_number = models.CharField(max_length=50, blank=True, null=True)

    is_kyc_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.business_name


class KYC(models.Model):
    seller = models.OneToOneField(SellerProfile, on_delete=models.CASCADE)

    pan_card = models.CharField(max_length=20)
    aadhaar_number = models.CharField(max_length=20)
    document = models.FileField(upload_to='kyc/')

    status = models.CharField(
        max_length=20,
        choices=[('pending','Pending'), ('approved','Approved'), ('rejected','Rejected')],
        default='pending'
    )


class BankAccount(models.Model):
    seller = models.OneToOneField(SellerProfile, on_delete=models.CASCADE)

    account_holder_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)


class Payout(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE)

    amount = models.FloatField()

    status = models.CharField(
        max_length=20,
        choices=[('pending','Pending'), ('processed','Processed'), ('failed','Failed')],
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)