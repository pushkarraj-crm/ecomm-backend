from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
from decimal import Decimal
from django.contrib.auth import authenticate
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDate
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import BasePermission, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError, MethodNotAllowed
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User
from customers.models import SupportTicket
from products.models import Product, Category, StoreBanner, DeliveryArea, ProductVariant
from products.selectors import catalog_products
from orders.models import (
    Order,
    SellerOrder,
    Payment,
    Refund,
    Coupon,
    CustomerOrderRequest,
)
from orders.serializers import OrderSerializer
from sellers.models import Payout, KYC
from core.pagination import ProductPagination
from .serializers import (
    UserRead,
    SellerWrite,
    CustomerWrite,
    ProductRead,
    ProductWrite,
    CategoryWrite,
    BannerWrite,
    DeliveryWrite,
    CouponWrite,
    RequestWrite,
    SupportWrite,
    InventoryWrite,
    EmployeeRead,
    EmployeeWrite,
    InvitationRead,
    InvitationWrite,
)


from .models import AdminEmployee, AdminInvitation


class IsWorkspaceAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not (
            user.is_authenticated
            and user.is_active
            and user.is_staff
            and not user.is_blacklisted
        ):
            return False
        if user.is_superuser:
            return True
        if view.kwargs.get("resource") in ("employees", "admin-invites"):
            return False
        employee = getattr(user, "admin_employee", None)
        return bool(
            employee
            and request.auth
            and request.auth.get("admin_version") == employee.session_version
        )


class AdminView(APIView):
    permission_classes = [IsAuthenticated, IsWorkspaceAdmin]


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        class Credentials(serializers.Serializer):
            email = serializers.EmailField()
            password = serializers.CharField(max_length=256, trim_whitespace=False)

        credentials = Credentials(data=request.data)
        credentials.is_valid(raise_exception=True)
        user = authenticate(**credentials.validated_data)
        employee = getattr(user, "admin_employee", None) if user else None
        if (
            not user
            or not user.is_staff
            or not (user.is_superuser or employee)
            or not user.is_active
            or user.is_blacklisted
        ):
            return Response({"error": "Invalid administrator credentials."}, status=401)
        refresh = RefreshToken.for_user(user)
        if employee and not user.is_superuser:
            refresh["admin_version"] = employee.session_version
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "email": user.email,
                "is_superuser": user.is_superuser,
                "is_employee": bool(employee and not user.is_superuser),
                "name": employee.full_name if employee else "Super Admin",
            }
        )


class MeView(AdminView):
    def get(self, request):
        employee = getattr(request.user, "admin_employee", None)
        return Response(
            {
                "email": request.user.email,
                "is_superuser": request.user.is_superuser,
                "is_employee": bool(employee and not request.user.is_superuser),
                "name": employee.full_name if employee else "Super Admin",
            }
        )


class OverviewView(AdminView):
    def get(self, request):
        report_zone = ZoneInfo("Asia/Kolkata")
        today = timezone.localdate(timezone=report_zone)
        start = today - timedelta(days=6)
        paid = Order.objects.filter(
            status__in=["paid", "partially_refunded", "refunded"]
        )
        gross = Decimal(str(paid.aggregate(total=Sum("total_amount"))["total"] or 0))
        refunds = (
            Decimal(
                Refund.objects.filter(status="processed").aggregate(
                    total=Sum("amount_paise")
                )["total"]
                or 0
            )
            / 100
        )
        daily = {
            row["day"]: row
            for row in paid.filter(
                created_at__gte=datetime.combine(start, time.min, tzinfo=report_zone)
            )
            .annotate(day=TruncDate("created_at", tzinfo=report_zone))
            .values("day")
            .annotate(total=Sum("total_amount"), count=Count("id"))
        }
        chart = [
            {
                "day": start + timedelta(days=i),
                "total": round(
                    daily.get(start + timedelta(days=i), {}).get("total", 0), 2
                ),
                "count": daily.get(start + timedelta(days=i), {}).get("count", 0),
            }
            for i in range(7)
        ]
        return Response(
            {
                "metrics": {
                    "net_sales": round(gross - refunds, 2),
                    "gross_sales": round(gross, 2),
                    "processed_refunds": refunds,
                    "paid_orders": paid.count(),
                    "sellers": User.objects.filter(
                        is_seller=True, is_superuser=False
                    ).count(),
                    "customers": User.objects.filter(
                        is_customer=True, is_seller=False, is_staff=False
                    ).count(),
                    "employees": (
                        AdminEmployee.objects.count()
                        if request.user.is_superuser
                        else None
                    ),
                    "products": Product.objects.count(),
                    "pending_sellers": User.objects.filter(
                        is_seller=True, seller_status="pending", is_superuser=False
                    ).count(),
                    "pending_products": Product.objects.filter(
                        status="pending"
                    ).count(),
                    "open_support": SupportTicket.objects.filter(status="open").count(),
                    "pending_requests": CustomerOrderRequest.objects.filter(
                        status="pending"
                    ).count(),
                    "low_stock": ProductVariant.objects.filter(stock__lte=5).count(),
                    "pending_kyc": KYC.objects.filter(status="pending").count(),
                    "pending_payouts": Payout.objects.filter(status="pending").count(),
                },
                "sales": chart,
                "recent_orders": OrderSerializer(
                    Order.objects.select_related("payment")
                    .prefetch_related(
                        "seller_orders__items__product_variant__product",
                        "seller_orders__refunds",
                        "seller_orders__customer_requests",
                    )
                    .order_by("-id")[:6],
                    many=True,
                ).data,
            }
        )


def resources():
    # Explicit allowlists: credentials, identity documents and bank details are never serialized here.
    return {
        "admin-invites": (
            AdminInvitation.objects.select_related("created_by"),
            InvitationRead,
            InvitationWrite,
            ["email"],
            ["is_active"],
            True,
        ),
        "employees": (
            AdminEmployee.objects.select_related("user", "created_by"),
            EmployeeRead,
            EmployeeWrite,
            ["full_name", "user__email"],
            [],
            True,
        ),
        "sellers": (
            User.objects.filter(is_seller=True, is_superuser=False).select_related(
                "seller_profile", "customer_profile"
            ),
            UserRead,
            SellerWrite,
            ["email", "seller_profile__store_name"],
            ["seller_status", "is_blacklisted"],
            False,
        ),
        "customers": (
            User.objects.filter(
                is_customer=True, is_seller=False, is_staff=False, is_superuser=False
            ).select_related("seller_profile", "customer_profile"),
            UserRead,
            CustomerWrite,
            ["email", "customer_profile__name"],
            ["is_active"],
            False,
        ),
        "products": (
            catalog_products(),
            ProductRead,
            ProductWrite,
            ["name", "seller__email"],
            ["status", "is_active"],
            False,
        ),
        "categories": (
            Category.objects.select_related("parent").annotate(
                child_count=Count("subcategories")
            ),
            CategoryWrite,
            CategoryWrite,
            ["name"],
            [],
            True,
        ),
        "banners": (
            StoreBanner.objects.all(),
            BannerWrite,
            BannerWrite,
            ["title"],
            ["is_active"],
            True,
        ),
        "delivery": (
            DeliveryArea.objects.all(),
            DeliveryWrite,
            DeliveryWrite,
            ["postal_code", "city"],
            ["is_active"],
            True,
        ),
        "coupons": (
            Coupon.objects.all(),
            CouponWrite,
            CouponWrite,
            ["code", "seller__email"],
            ["is_active"],
            True,
        ),
        "inventory": (
            ProductVariant.objects.select_related("product"),
            None,
            InventoryWrite,
            ["product__name"],
            [],
            False,
        ),
        "orders": (
            Order.objects.select_related("payment").prefetch_related(
                "seller_orders__items__product_variant__product",
                "seller_orders__refunds",
                "seller_orders__customer_requests",
            ),
            OrderSerializer,
            None,
            ["email", "name"],
            ["status"],
            False,
        ),
        "requests": (
            CustomerOrderRequest.objects.select_related("seller_order__order"),
            None,
            RequestWrite,
            ["reason", "seller_order__order__email"],
            ["status", "kind"],
            False,
        ),
        "support": (
            SupportTicket.objects.select_related("user"),
            None,
            SupportWrite,
            ["subject", "user__email"],
            ["status"],
            False,
        ),
        "refunds": (Refund.objects.all(), None, None, ["reason"], ["status"], False),
        "payouts": (
            Payout.objects.select_related("seller"),
            None,
            None,
            ["seller__store_name"],
            ["status"],
            False,
        ),
        "activity": (
            LogEntry.objects.select_related("user"),
            None,
            None,
            ["object_repr", "user__email"],
            [],
            False,
        ),
    }


def record_data(resource, obj, serializer=None):
    if serializer:
        return serializer(obj).data
    if resource == "inventory":
        return {
            "id": obj.id,
            "product_name": obj.product.name,
            "size": obj.size,
            "color": obj.color,
            "price": obj.price,
            "original_price": obj.original_price,
            "stock": obj.stock,
        }
    if resource == "requests":
        return {
            "id": obj.id,
            "order_id": obj.seller_order.order_id,
            "seller_order": obj.seller_order_id,
            "customer": obj.seller_order.order.email,
            "kind": obj.kind,
            "reason": obj.reason,
            "status": obj.status,
            "response": obj.response,
            "created_at": obj.created_at,
        }
    if resource == "support":
        return {
            "id": obj.id,
            "customer": obj.user.email,
            "subject": obj.subject,
            "message": obj.message,
            "status": obj.status,
            "response": obj.response,
            "created_at": obj.created_at,
        }
    if resource == "refunds":
        return {
            "id": obj.id,
            "seller_order": obj.seller_order_id,
            "amount": obj.amount_paise / 100,
            "reason": obj.reason,
            "status": obj.status,
            "created_at": obj.created_at,
        }
    if resource == "payouts":
        return {
            "id": obj.id,
            "seller": obj.seller_id,
            "store_name": obj.seller.store_name or obj.seller.business_name,
            "amount": obj.amount,
            "status": obj.status,
            "created_at": obj.created_at,
        }
    if resource == "activity":
        return {
            "id": obj.id,
            "actor": obj.user.email,
            "record": obj.object_repr,
            "action": obj.get_action_flag_display(),
            "change": obj.change_message,
            "created_at": obj.action_time,
        }
    raise Http404


class ResourceView(AdminView):
    def spec(self, resource):
        spec = resources().get(resource)
        if not spec:
            raise Http404
        return spec

    def get(self, request, resource, pk=None):
        queryset, read, write, search_fields, filter_fields, create = self.spec(
            resource
        )
        if pk is not None:
            obj = queryset.filter(pk=pk).first()
            if not obj:
                raise Http404
            data = record_data(resource, obj, read)
            if resource == "categories":
                data["children"] = CategoryWrite(
                    Category.objects.filter(parent_id=obj.pk)
                    .select_related("parent")
                    .annotate(child_count=Count("subcategories"))
                    .order_by("name")[:100],
                    many=True,
                ).data
            if resource == "sellers":
                profile = getattr(obj, "seller_profile", None)
                fields = [
                    "business_name",
                    "store_name",
                    "owner_full_name",
                    "business_type",
                    "gst_registered",
                    "gst_number",
                    "gst_legal_name",
                    "gst_verification_status",
                    "is_kyc_verified",
                    "pickup_address_line_1",
                    "pickup_address_line_2",
                    "pickup_landmark",
                    "pickup_city",
                    "pickup_state",
                    "pickup_postal_code",
                    "pickup_country",
                ]
                data["business_profile"] = (
                    {name: getattr(profile, name) for name in fields}
                    if profile
                    else None
                )
                products = catalog_products().filter(seller_id=obj.pk).order_by("-id")
                data["catalog_summary"] = {
                    "total": products.count(),
                    "approved": products.filter(status="approved").count(),
                    "pending": products.filter(status="pending").count(),
                    "shipments": SellerOrder.objects.filter(seller_id=obj.pk).count(),
                }
                data["products"] = ProductRead(products[:20], many=True).data
            return Response(data)
        if resource == "products" and request.query_params.get("seller"):
            seller_filter = serializers.IntegerField(min_value=1).run_validation(
                request.query_params["seller"]
            )
            queryset = queryset.filter(seller_id=seller_filter)
        search = request.query_params.get("search", "").strip()
        if len(search) > 100:
            raise ValidationError({"search": "Use at most 100 characters."})
        if search:
            query = Q()
            for field in search_fields:
                query |= Q(**{field + "__icontains": search})
            if search.isdigit():
                query |= Q(pk=int(search))
            queryset = queryset.filter(query)
        for field in filter_fields:
            value = request.query_params.get(field)
            if value is not None and value != "":
                if field.startswith("is_"):
                    if value not in ("true", "false"):
                        raise ValidationError({field: "Use true or false."})
                    value = value == "true"
                queryset = queryset.filter(**{field: value})
        pager = ProductPagination()
        page = pager.paginate_queryset(queryset.order_by("-pk"), request, view=self)
        return pager.get_paginated_response(
            [record_data(resource, obj, read) for obj in page]
        )

    @transaction.atomic
    def post(self, request, resource, pk=None):
        queryset, read, write, search, filters, create = self.spec(resource)
        if not create or pk is not None:
            raise MethodNotAllowed("POST")
        return self.save(request, resource, read, write, None)

    @transaction.atomic
    def patch(self, request, resource, pk):
        queryset, read, write, search, filters, create = self.spec(resource)
        if not write:
            raise MethodNotAllowed("PATCH")
        # Lock the base row, not the annotated/grouped catalog query. PostgreSQL
        # does not allow FOR UPDATE with GROUP BY or nullable outer joins.
        try:
            queryset.model.objects.select_for_update().get(pk=pk)
        except queryset.model.DoesNotExist:
            raise Http404
        obj = queryset.filter(pk=pk).first()
        if not obj:
            raise Http404
        return self.save(request, resource, read, write, obj)

    def save(self, request, resource, read, write, obj):
        allowed = {key for key, field in write().fields.items() if not field.read_only}
        unknown = set(request.data) - allowed
        if unknown:
            raise ValidationError(
                {key: "This field cannot be edited here." for key in unknown}
            )
        if not request.data:
            raise ValidationError("Provide at least one editable field.")
        serializer = write(
            obj,
            data=request.data,
            partial=obj is not None,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        LogEntry.objects.log_action(
            user_id=request.user.pk,
            content_type_id=ContentType.objects.get_for_model(instance).pk,
            object_id=str(instance.pk),
            object_repr=str(instance)[:200],
            action_flag=CHANGE if obj else ADDITION,
            change_message="Updated fields: "
            + ", ".join(
                "password (reset)" if name == "password" else name
                for name in sorted(serializer.validated_data)
            ),
        )
        # Refresh annotated catalog data after approval changes.
        if resource == "products":
            instance = catalog_products().get(pk=instance.pk)
        return Response(
            record_data(resource, instance, read), status=200 if obj else 201
        )


class SuperAdminSignupView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "register"

    @transaction.atomic
    def post(self, request):
        import hashlib
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as PasswordValidationError
        from django.db import IntegrityError

        class SignupInput(serializers.Serializer):
            email = serializers.EmailField()
            password = serializers.CharField(max_length=256, trim_whitespace=False)
            token = serializers.CharField(min_length=20, max_length=128)

        serializer = SignupInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        invitation = (
            AdminInvitation.objects.select_for_update()
            .filter(token_hash=hashlib.sha256(data["token"].encode()).hexdigest())
            .first()
        )
        creator = invitation.created_by if invitation else None
        if (
            not invitation
            or invitation.used_at
            or not invitation.is_active
            or invitation.expires_at <= timezone.now()
            or not creator
            or not creator.is_active
            or not creator.is_staff
            or not creator.is_superuser
            or creator.is_blacklisted
        ):
            raise ValidationError(
                {
                    "token": "This invitation is invalid, expired, used or revoked. Request a new link from an existing super-admin."
                }
            )
        email = data["email"].strip().lower()
        if email != invitation.email.lower():
            raise ValidationError(
                {"email": "Use the email address this invitation was created for."}
            )
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                {"email": "An account already exists for this email."}
            )
        try:
            validate_password(data["password"], user=User(email=email))
        except PasswordValidationError as error:
            raise ValidationError({"password": error.messages})
        try:
            with transaction.atomic():
                user = User.objects.create_superuser(
                    email=email, password=data["password"]
                )
                user.is_customer = False
                user.is_seller = False
                user.save(update_fields=["is_customer", "is_seller"])
        except IntegrityError:
            raise ValidationError(
                {"email": "An account already exists for this email."}
            )
        invitation.used_at = timezone.now()
        invitation.used_by = user
        invitation.save(update_fields=["used_at", "used_by"])
        LogEntry.objects.log_action(
            user_id=creator.pk,
            content_type_id=ContentType.objects.get_for_model(user).pk,
            object_id=str(user.pk),
            object_repr=user.email,
            action_flag=ADDITION,
            change_message="Super-admin registered using a single-use invitation.",
        )
        return Response(
            {"message": "Super-admin account created. You can now sign in."}, status=201
        )
