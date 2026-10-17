from .order_workspace import SellerOrderWorkspaceView, SellerOrderWorkspaceDetailView
from django.urls import path
from .catalog_submit import SellerCatalogSubmitView
from .image_checks import SellerImageCheckView
from orders.views import (
    SellerDashboardAPIView,
    OrderStatusUpdateAPIView,
    ShipmentTrackingView,
)
from products.views import CreateProductView
from .views import (
    SellerInventoryAPIView,
    SellerInventoryStockAPIView,
    SellerInventorySummaryAPIView,
    SellerOrderInvoiceAPIView,
    SellerOrderRefundAPIView,
    SellerOrderListAPIView,
    SellerEarningsAPIView,
    SellerBusinessAnalyticsAPIView,
    SellerBulkCatalogAPIView,
    SellerBulkCatalogTemplateAPIView,
    SellerProfileAPIView,
    KYCAPIView,
    BankAPIView,
    BankVerificationAPIView,
    BankVerificationConfirmAPIView,
    PayoutAPIView,
)

from .catalog import (
    SellerCatalogAPIView,
    SellerCatalogDetailAPIView,
    SellerCatalogSummaryAPIView,
)

urlpatterns = [
    path("orders/workspace/", SellerOrderWorkspaceView.as_view()),
    path("orders/<int:pk>/details/", SellerOrderWorkspaceDetailView.as_view()),
    path("orders/<int:pk>/tracking/", ShipmentTrackingView.as_view()),
    path("catalog/", SellerCatalogAPIView.as_view()),
    path("catalog/submit/", SellerCatalogSubmitView.as_view()),
    path("catalog/images/check/", SellerImageCheckView.as_view()),
    path("catalog/summary/", SellerCatalogSummaryAPIView.as_view()),
    path("catalog/<int:product_id>/", SellerCatalogDetailAPIView.as_view()),
    path("dashboard/", SellerDashboardAPIView.as_view()),
    path("orders/", SellerOrderListAPIView.as_view()),
    path("analytics/", SellerBusinessAnalyticsAPIView.as_view()),
    path("catalog/bulk/template/", SellerBulkCatalogTemplateAPIView.as_view()),
    path("catalog/bulk/", SellerBulkCatalogAPIView.as_view()),
    path("catalog/single/", CreateProductView.as_view()),
    path("orders/<int:pk>/invoice/", SellerOrderInvoiceAPIView.as_view()),
    path("orders/<int:pk>/refunds/", SellerOrderRefundAPIView.as_view()),
    path("earnings/", SellerEarningsAPIView.as_view()),
    path("inventory/summary/", SellerInventorySummaryAPIView.as_view()),
    path("inventory/", SellerInventoryAPIView.as_view()),
    path("inventory/<int:variant_id>/", SellerInventoryStockAPIView.as_view()),
    path("orders/update/<int:pk>/", OrderStatusUpdateAPIView.as_view()),
    path("kyc/", KYCAPIView.as_view()),
    path("profile/", SellerProfileAPIView.as_view()),
    path("bank/", BankAPIView.as_view()),
    path("bank/verification/", BankVerificationAPIView.as_view()),
    path("bank/verification/confirm/", BankVerificationConfirmAPIView.as_view()),
    path("payout/", PayoutAPIView.as_view()),
]
