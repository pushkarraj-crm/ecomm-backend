from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0002_product_product_catalog_idx'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='productvariant',
            index=models.Index(fields=['product', 'stock'], name='variant_product_stock_idx'),
        ),
        migrations.CreateModel(
            name='ProductInteraction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(choices=[('view', 'View'), ('click', 'Click')], max_length=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='interactions', to='products.product')),
            ],
        ),
        migrations.AddIndex(
            model_name='productinteraction',
            index=models.Index(fields=['product', 'created_at', 'event'], name='product_date_event_idx'),
        ),
    ]
