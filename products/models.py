from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError


# =========================
# 📂 CATEGORY
# =========================
class Category(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="categories/", blank=True)

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
    RETURN_POLICY_CHOICES = (
        ('no_return', 'No return'),
        ('return_and_exchange', 'Return and exchange'),
    )
    RETURN_DAY_CHOICES = ((2, '2 days'), (5, '5 days'), (7, '7 days'))

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    specifications = models.JSONField(default=dict, blank=True)
    size_guide = models.TextField(blank=True, max_length=4000)
    return_policy = models.CharField(
        max_length=24,
        choices=RETURN_POLICY_CHOICES,
        default='no_return',
    )
    return_days = models.PositiveSmallIntegerField(
        choices=RETURN_DAY_CHOICES,
        null=True,
        blank=True,
    )

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
    original_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['product', 'stock'], name='variant_product_stock_idx')]

    def clean(self):
        if self.price <= 0 or self.stock < 0:
            raise ValidationError("Price must be positive and stock cannot be negative.")
        if self.original_price is not None and float(self.original_price) < self.price:
            raise ValidationError({"original_price": "Must be at least the selling price."})

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


class StoreBanner(models.Model):
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=250, blank=True)
    image = models.ImageField(upload_to='banners/', blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']

    def __str__(self):
        return self.title


class DeliveryArea(models.Model):
    postal_code = models.CharField(max_length=6, unique=True)
    city = models.CharField(max_length=100)
    min_days = models.PositiveSmallIntegerField(default=3)
    max_days = models.PositiveSmallIntegerField(default=7)
    is_active = models.BooleanField(default=True)

    def clean(self):
        if len(self.postal_code) != 6 or not self.postal_code.isdigit():
            raise ValidationError('Enter a six-digit Indian pincode.')
        if self.min_days > self.max_days:
            raise ValidationError('Maximum delivery days must be at least the minimum.')

    def __str__(self):
        return f'{self.postal_code} — {self.city}'
