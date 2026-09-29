from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_financial_order_status(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    Order.objects.filter(payment__status='paid').update(status='paid')
    Order.objects.filter(payment__status='failed').update(status='failed')
    # Legacy orders without a Payment row were treated as paid by the existing
    # customer order history API, so preserve that behavior.
    Order.objects.filter(payment__isnull=True).update(status='paid')


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0004_order_address_line_1_order_address_line_2_order_city_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Payment Pending'),
                    ('paid', 'Paid'),
                    ('failed', 'Payment Failed'),
                    ('partially_refunded', 'Partially Refunded'),
                    ('refunded', 'Refunded'),
                ],
                db_index=True,
                default='pending',
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_financial_order_status, migrations.RunPython.noop),
        migrations.CreateModel(
            name='Refund',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('idempotency_key', models.CharField(max_length=64)),
                ('amount_paise', models.PositiveBigIntegerField()),
                ('reason', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processed', 'Processed'), ('failed', 'Failed')], default='pending', max_length=10)),
                ('razorpay_refund_id', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('failure_reason', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('payment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='refunds', to='orders.payment')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seller_refunds', to=settings.AUTH_USER_MODEL)),
                ('seller_order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='refunds', to='orders.sellerorder')),
            ],
        ),
        migrations.AddConstraint(
            model_name='refund',
            constraint=models.UniqueConstraint(fields=('requested_by', 'idempotency_key'), name='refund_seller_idem_uniq'),
        ),
        migrations.AddIndex(
            model_name='refund',
            index=models.Index(fields=['seller_order', 'status'], name='refund_order_status_idx'),
        ),
    ]
