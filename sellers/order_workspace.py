"""Seller-owned order workspace with server filters and bounded CSV exports."""

import csv
from datetime import timedelta
from django.db.models import Q, Exists, OuterRef
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from accounts.permissions import IsSeller
from orders.models import SellerOrder, CustomerOrderRequest
from orders.serializers import SellerOrderSerializer
from core.pagination import ProductPagination


class WorkspaceQuery(serializers.Serializer):
    tab = serializers.ChoiceField(
        choices=[
            "on_hold",
            "pending",
            "ready_to_ship",
            "shipped",
            "cancelled",
            "delivered",
        ],
        default="pending",
    )
    search = serializers.CharField(max_length=100, required=False, allow_blank=True)
    search_by = serializers.ChoiceField(choices=["sku", "order"], default="sku")
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    export = serializers.ChoiceField(choices=["csv"], required=False)

    def validate(self, attrs):
        if attrs.get("start") and attrs.get("end") and attrs["start"] > attrs["end"]:
            raise serializers.ValidationError("Start date must be before end date.")
        return attrs


class SellerOrderWorkspaceView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        query = WorkspaceQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        cancelled = Q(workspace_cancelled=True)
        held = Q(order__payment__status__in=["pending", "failed"]) | Q(
            order__status="refunded", status="pending"
        )
        ready = Q(status="pending") & ~Q(tracking_number="")
        filters = {
            "cancelled": cancelled,
            "on_hold": held & ~cancelled,
            "pending": Q(status="pending", tracking_number="") & ~held & ~cancelled,
            "ready_to_ship": ready & ~held & ~cancelled,
            "shipped": Q(status="shipped") & ~held & ~cancelled,
            "delivered": Q(status="delivered") & ~held & ~cancelled,
        }
        base = SellerOrder.objects.filter(seller=request.user).annotate(
            workspace_cancelled=Exists(
                CustomerOrderRequest.objects.filter(
                    seller_order_id=OuterRef("pk"),
                    kind="cancel",
                    status__in=["approved", "resolved"],
                )
            )
        )
        if data.get("start"):
            base = base.filter(order__created_at__date__gte=data["start"])
        if data.get("end"):
            base = base.filter(order__created_at__date__lte=data["end"])
        if data.get("search"):
            value = data["search"]
            if (
                not value.isascii()
                or not value.isdigit()
                or len(value) > 19
                or int(value) > 9223372036854775807
            ):
                raise serializers.ValidationError(
                    {"search": "Enter a numeric SKU ID or Order ID."}
                )
            base = base.filter(
                **(
                    {"items__product_variant_id": int(value)}
                    if data["search_by"] == "sku"
                    else {"order_id": int(value)}
                )
            )
        counts = {
            key: base.filter(condition).distinct().count()
            for key, condition in filters.items()
        }
        orders = (
            base.filter(filters[data["tab"]])
            .distinct()
            .select_related("order", "order__payment")
            .prefetch_related(
                "items__product_variant__product", "refunds", "customer_requests"
            )
            .order_by("-id")
        )
        health = {
            "awaiting_dispatch": counts["pending"] + counts["ready_to_ship"],
            "overdue": base.filter(
                filters["pending"] | filters["ready_to_ship"],
                created_at__lt=timezone.now() - timedelta(days=2),
            )
            .distinct()
            .count(),
            "shipped": counts["shipped"],
            "delivered": counts["delivered"],
        }
        if data.get("export"):
            if orders.count() > 10000:
                raise serializers.ValidationError(
                    "Narrow the date range to export at most 10,000 orders."
                )
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="orders.csv"'
            writer = csv.writer(response)
            writer.writerow(
                [
                    "Order ID",
                    "Seller order ID",
                    "SKU IDs",
                    "Products",
                    "Status",
                    "Order date",
                    "Amount",
                ]
            )

            def safe(value):
                text = str(value)
                return (
                    "'" + text
                    if text.lstrip().startswith(("=", "+", "-", "@"))
                    else text
                )

            for order in orders:
                writer.writerow(
                    [
                        order.order_id,
                        order.pk,
                        ",".join(
                            str(item.product_variant_id) for item in order.items.all()
                        ),
                        safe(
                            ", ".join(
                                item.product_variant.product.name
                                for item in order.items.all()
                            )
                        ),
                        data["tab"],
                        order.order.created_at.isoformat(),
                        order.total_amount,
                    ]
                )
            return response
        paginator = ProductPagination()
        page = paginator.paginate_queryset(orders, request, view=self)
        response = paginator.get_paginated_response(
            SellerOrderSerializer(page, many=True).data
        )
        response.data.update({"counts": counts, "dispatch": health})
        return response


class SellerOrderWorkspaceDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request, pk):
        from django.shortcuts import get_object_or_404
        from rest_framework.response import Response

        order = get_object_or_404(
            SellerOrder.objects.filter(seller=request.user)
            .select_related("order", "order__payment")
            .prefetch_related(
                "items__product_variant__product", "refunds", "customer_requests"
            ),
            pk=pk,
        )
        return Response({"results": [SellerOrderSerializer(order).data]})
