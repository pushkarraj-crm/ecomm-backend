from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError


# =========================
# 📂 CATEGORY
# =========================
class Category(models.Model):
    name = models.CharField(max_length=100)

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent == self:
            raise ValidationError("Category cannot be parent of itself")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


# =========================
# 🛍️ PRODUCT
# =========================
class Product(models.Model):
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'is_active'], name='product_catalog_idx')]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            count = 1

            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{count}"
                count += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# =========================
# 🔥 PRODUCT VARIANT
# =========================
class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')

    size = models.CharField(max_length=50)
    color = models.CharField(max_length=50)

    price = models.FloatField()
    stock = models.IntegerField()

    class Meta:
        indexes = [models.Index(fields=['product', 'stock'], name='variant_product_stock_idx')]

    def __str__(self):
        return f"{self.product.name} - {self.size} - {self.color}"


# =========================
# 🖼️ VARIANT IMAGES
# =========================
class ProductImage(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')

    def __str__(self):
        return f"Image for {self.variant}"


# =========================
# ⭐ REVIEWS
# =========================
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField()
    comment = models.TextField(blank=True)


class ProductInteraction(models.Model):
    EVENT_CHOICES = (('view', 'View'), ('click', 'Click'))

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='interactions')
    event = models.CharField(max_length=8, choices=EVENT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['product', 'created_at', 'event'], name='product_date_event_idx'),
        ]
