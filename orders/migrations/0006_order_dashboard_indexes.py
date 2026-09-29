from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_order_status_refund'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')], db_index=True, default='pending', max_length=10),
        ),
        migrations.AddIndex(
            model_name='sellerorder',
            index=models.Index(fields=['seller', 'status'], name='seller_order_status_idx'),
        ),
        migrations.AddIndex(
            model_name='sellerorder',
            index=models.Index(fields=['seller', 'created_at'], name='seller_order_date_idx'),
        ),
    ]
