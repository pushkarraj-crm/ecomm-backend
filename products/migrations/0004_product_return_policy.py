from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_productinteraction_variant_product_stock_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='return_policy',
            field=models.CharField(
                choices=[('no_return', 'No return'), ('return_and_exchange', 'Return and exchange')],
                default='no_return',
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='return_days',
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[(2, '2 days'), (5, '5 days'), (7, '7 days')],
                null=True,
            ),
        ),
    ]
