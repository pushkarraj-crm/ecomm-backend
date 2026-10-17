from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers
from accounts.models import User
from customers.models import SupportTicket
from products.models import Product, Category, StoreBanner, DeliveryArea, ProductVariant
from products.serializers import ProductReadSerializer
from orders.models import Coupon, CustomerOrderRequest


class ValidatedModelSerializer(serializers.ModelSerializer):
    def validate_image(self, value):
        if value and value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Images must be smaller than 2 MB.")
        return value

    def validate(self, attrs):
        instance = (
            self.instance.__class__.objects.get(pk=self.instance.pk)
            if self.instance
            else self.Meta.model()
        )
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.full_clean(
                exclude=[
                    field.name
                    for field in instance._meta.fields
                    if field.name not in self.fields
                ]
            )
        except ModelValidationError as error:
            raise serializers.ValidationError(
                error.message_dict if hasattr(error, "message_dict") else error.messages
            )
        return attrs


class UserRead(serializers.ModelSerializer):
    store_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()

    def get_store_name(self, obj):
        profile = getattr(obj, "seller_profile", None)
        return (profile.store_name or profile.business_name) if profile else ""

    def get_name(self, obj):
        profile = getattr(obj, "customer_profile", None)
        seller_profile = getattr(obj, "seller_profile", None)
        return (
            profile.name
            if profile
            else (seller_profile.owner_full_name if seller_profile else "")
        )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "store_name",
            "is_seller",
            "seller_status",
            "is_blacklisted",
            "is_active",
            "last_login",
        ]


class SellerWrite(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["seller_status", "is_blacklisted"]


class CustomerWrite(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["is_active"]


class ProductRead(ProductReadSerializer):
    class Meta(ProductReadSerializer.Meta):
        fields = ProductReadSerializer.Meta.fields + [
            "status",
            "is_active",
            "created_at",
        ]


class ProductWrite(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["status", "is_active"]


class CategoryWrite(ValidatedModelSerializer):
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, default=None
    )
    subcategory_count = serializers.SerializerMethodField()

    def get_subcategory_count(self, obj):
        return (
            obj.child_count
            if hasattr(obj, "child_count")
            else obj.subcategories.count()
        )

    class Meta:
        model = Category
        fields = ["id", "name", "parent", "parent_name", "subcategory_count", "image"]
        read_only_fields = ["id", "parent_name", "subcategory_count"]

    def validate_parent(self, value):
        seen = {self.instance.pk} if self.instance else set()
        current = value
        while current:
            if current.pk in seen:
                raise serializers.ValidationError(
                    "Category hierarchy cannot contain a cycle."
                )
            seen.add(current.pk)
            current = current.parent
        return value


class BannerWrite(ValidatedModelSerializer):
    class Meta:
        model = StoreBanner
        fields = [
            "id",
            "title",
            "subtitle",
            "image",
            "category",
            "is_active",
            "position",
        ]
        read_only_fields = ["id"]


class DeliveryWrite(ValidatedModelSerializer):
    class Meta:
        model = DeliveryArea
        fields = ["id", "postal_code", "city", "min_days", "max_days", "is_active"]
        read_only_fields = ["id"]


class CouponWrite(ValidatedModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "seller",
            "percent",
            "minimum_subtotal",
            "starts_at",
            "expires_at",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate_code(self, value):
        return value.strip().upper()

    def validate_seller(self, value):
        if not value.is_seller or value.is_superuser:
            raise serializers.ValidationError("Choose a seller account.")
        return value


class RequestWrite(serializers.ModelSerializer):
    class Meta:
        model = CustomerOrderRequest
        fields = ["status", "response"]


class SupportWrite(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["status", "response"]


class InventoryWrite(ValidatedModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["price", "original_price", "stock"]


from django.contrib.auth.password_validation import validate_password
from .models import AdminEmployee


class EmployeeRead(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)

    class Meta:
        model = AdminEmployee
        fields = ["id", "full_name", "email", "is_active", "last_login", "created_at"]


class EmployeeWrite(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email")
    is_active = serializers.BooleanField(source="user.is_active", required=False)
    password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False, max_length=256
    )

    class Meta:
        model = AdminEmployee
        fields = ["full_name", "email", "is_active", "password"]

    def validate(self, attrs):
        account = attrs.get("user", {})
        email = account.get("email", self.instance.user.email if self.instance else "")
        matches = User.objects.filter(email__iexact=email)
        if self.instance:
            matches = matches.exclude(pk=self.instance.user_id)
        if matches.exists():
            raise serializers.ValidationError(
                {"email": "An account already exists for this email."}
            )
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": "Set an initial employee password."}
            )
        if "password" in attrs:
            try:
                validate_password(
                    attrs["password"],
                    user=self.instance.user if self.instance else User(email=email),
                )
            except ModelValidationError as error:
                raise serializers.ValidationError({"password": error.messages})
        return attrs

    def create(self, attrs):
        account = attrs.pop("user")
        password = attrs.pop("password")
        user = User.objects.create_user(email=account["email"], password=password)
        user.is_staff = True
        user.is_customer = False
        user.is_seller = False
        user.is_superuser = False
        user.is_active = account.get("is_active", True)
        user.save()
        return AdminEmployee.objects.create(
            user=user, created_by=self.context["request"].user, **attrs
        )

    def update(self, instance, attrs):
        account = attrs.pop("user", {})
        password = attrs.pop("password", None)
        user = instance.user
        revoke = password is not None or any(
            getattr(user, key) != value for key, value in account.items()
        )
        for key, value in account.items():
            setattr(user, key, value)
        if password is not None:
            user.set_password(password)
        user.save()
        if "full_name" in attrs:
            instance.full_name = attrs["full_name"]
        if revoke:
            instance.session_version += 1
        instance.save()
        return instance


from .models import AdminInvitation


class InvitationRead(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    signup_token = serializers.SerializerMethodField()

    class Meta:
        model = AdminInvitation
        fields = [
            "id",
            "email",
            "status",
            "is_active",
            "expires_at",
            "used_at",
            "created_at",
            "signup_token",
        ]

    def get_status(self, obj):
        from django.utils import timezone

        if obj.used_at:
            return "used"
        if not obj.is_active:
            return "revoked"
        return "expired" if obj.expires_at <= timezone.now() else "pending"

    def get_signup_token(self, obj):
        return getattr(obj, "_signup_token", None)


class InvitationWrite(serializers.ModelSerializer):
    class Meta:
        model = AdminInvitation
        fields = ["email", "is_active"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account already exists for this email. Use a different email for a new super-admin account."
            )
        return value

    def validate(self, attrs):
        if self.instance and "email" in attrs and attrs["email"] != self.instance.email:
            raise serializers.ValidationError(
                {"email": "Create a new invitation to change the recipient."}
            )
        return attrs

    def create(self, attrs):
        import secrets, hashlib

        token = secrets.token_urlsafe(32)
        instance = AdminInvitation.objects.create(
            created_by=self.context["request"].user,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            **attrs,
        )
        instance._signup_token = token
        return instance
