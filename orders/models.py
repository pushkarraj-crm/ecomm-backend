from django.db import models
from django.conf import settings
from products.models import ProductVariant


# =========================
# MAIN ORDER (Customer)
# =========================
class Order(models.Model):
    STATUS_CHOICES = (
        ("pending", "Payment Pending"),
        ("paid", "Paid"),
        ("failed", "Payment Failed"),
        ("partially_refunded", "Partially Refunded"),
        ("refunded", "Refunded"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",  # 🔥 add this (useful for user.orders)
    )

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    address = models.TextField()
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="India")

    # Financial state for the customer order. SellerOrder.status separately
    # tracks seller fulfillment (pending, shipped, delivered).
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    total_amount = models.FloatField(default=0)
    coupon_code = models.CharField(max_length=40, blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.email}"


class Payment(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    )

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="payment",
    )
    razorpay_order_id = models.CharField(
        max_length=64, unique=True, null=True, blank=True
    )
    razorpay_payment_id = models.CharField(
        max_length=64, unique=True, null=True, blank=True
    )
    amount_paise = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment for order #{self.order_id} ({self.status})"


# =========================
# SELLER ORDER
# =========================
class SellerOrder(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="seller_orders",  # ✅ already correct
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_orders",  # 🔥 ADD THIS (important)
    )

    total_amount = models.FloatField(default=0)
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=150, blank=True)
    tracking_url = models.URLField(blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)  # 🔥 add this

    class Meta:
        indexes = [
            models.Index(fields=["seller", "status"], name="seller_order_status_idx"),
            models.Index(fields=["seller", "created_at"], name="seller_order_date_idx"),
        ]

    def __str__(self):
        return f"{self.seller.email} - Order {self.id}"


# =========================
# ORDER ITEMS
# =========================
class OrderItem(models.Model):
    seller_order = models.ForeignKey(
        SellerOrder,
        on_delete=models.CASCADE,
        related_name="items",  # ✅ already correct
    )

    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)

    return_policy = models.CharField(max_length=24, null=True, blank=True)
    return_days = models.PositiveSmallIntegerField(null=True, blank=True)
    quantity = models.IntegerField()
    price = models.FloatField()  # price at purchase time

    def __str__(self):
        return f"{self.product_variant} x {self.quantity}"


class Refund(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    )

    seller_order = models.ForeignKey(
        SellerOrder,
        on_delete=models.CASCADE,
        related_name="refunds",
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="refunds",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_refunds",
    )
    idempotency_key = models.CharField(max_length=64)
    amount_paise = models.PositiveBigIntegerField()
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    razorpay_refund_id = models.CharField(
        max_length=64, unique=True, null=True, blank=True
    )
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["requested_by", "idempotency_key"],
                name="refund_seller_idem_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["seller_order", "status"], name="refund_order_status_idx"
            ),
        ]

    def __str__(self):
        return (
            f"Refund {self.id} for seller order #{self.seller_order_id} ({self.status})"
        )


class CustomerOrderRequest(models.Model):
    seller_order = models.ForeignKey(
        SellerOrder, related_name="customer_requests", on_delete=models.CASCADE
    )
    kind = models.CharField(
        max_length=12,
        choices=[
            ("cancel", "Cancellation"),
            ("return", "Return"),
            ("refund", "Refund enquiry"),
        ],
    )
    reason = models.TextField(max_length=2000)
    status = models.CharField(
        max_length=12,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("resolved", "Resolved"),
        ],
    )
    response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seller_order", "kind"], name="customer_request_order_kind"
            )
        ]


class Coupon(models.Model):
    code = models.CharField(max_length=40, unique=True)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={"is_seller": True},
    )
    percent = models.PositiveSmallIntegerField(
        help_text="Seller-funded percentage, applied to this seller’s items only."
    )
    minimum_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=False)

    def clean(self):
        from django.core.exceptions import ValidationError

        if not 1 <= self.percent <= 95:
            raise ValidationError("Discount must be between 1 and 95 percent.")
        if self.starts_at and self.expires_at and self.starts_at >= self.expires_at:
            raise ValidationError("Expiry must follow the start time.")
        if self.minimum_subtotal < 0:
            raise ValidationError("Minimum subtotal cannot be negative.")

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.code
