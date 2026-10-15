from django.db import migrations, models


def copy_legacy_store_names(apps, schema_editor):
    SellerProfile = apps.get_model('sellers', 'SellerProfile')
    for profile in SellerProfile.objects.filter(store_name='').only('id', 'business_name').iterator():
        profile.store_name = profile.business_name
        profile.save(update_fields=['store_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('sellers', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerprofile',
            name='store_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='owner_full_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='business_type',
            field=models.CharField(blank=True, choices=[('individual', 'Individual'), ('sole_proprietorship', 'Sole proprietorship'), ('partnership', 'Partnership'), ('llp', 'Limited liability partnership'), ('private_limited', 'Private limited company'), ('public_limited', 'Public limited company'), ('other', 'Other')], max_length=32),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='gst_registered',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='gst_legal_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='gst_registered_address',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='gst_verification_status',
            field=models.CharField(choices=[('not_required', 'Not required'), ('pending', 'Pending'), ('verified', 'Verified'), ('failed', 'Failed')], default='not_required', max_length=16),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='gst_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='use_gst_registered_address',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='pickup_address_line_1',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='pickup_address_line_2',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='pickup_landmark',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='pickup_city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='pickup_state',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='pickup_postal_code',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='sellerprofile',
            name='pickup_country',
            field=models.CharField(default='India', max_length=100),
        ),
        migrations.RunPython(copy_legacy_store_names, migrations.RunPython.noop),
        migrations.AddField(
            model_name='bankaccount',
            name='verification_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('amount_confirmation', 'Amount confirmation'), ('verified', 'Verified'), ('failed', 'Failed')], default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='verified_account_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='verification_reference',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='razorpay_contact_id',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='razorpay_fund_account_id',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='validation_amount_paise',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='verification_attempts',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
