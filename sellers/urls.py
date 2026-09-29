from django.urls import path
from orders.views import SellerDashboardAPIView, OrderStatusUpdateAPIView
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
    KYCAPIView,
    BankAPIView,
    PayoutAPIView,
)

urlpatterns = [
    path('dashboard/', SellerDashboardAPIView.as_view()),
    path('orders/', SellerOrderListAPIView.as_view()),
    path('analytics/', SellerBusinessAnalyticsAPIView.as_view()),
    path('catalog/bulk/template/', SellerBulkCatalogTemplateAPIView.as_view()),
    path('catalog/bulk/', SellerBulkCatalogAPIView.as_view()),
    path('catalog/single/', CreateProductView.as_view()),
    path('orders/<int:pk>/invoice/', SellerOrderInvoiceAPIView.as_view()),
    path('orders/<int:pk>/refunds/', SellerOrderRefundAPIView.as_view()),
    path('earnings/', SellerEarningsAPIView.as_view()),
    path('inventory/summary/', SellerInventorySummaryAPIView.as_view()),
    path('inventory/', SellerInventoryAPIView.as_view()),
    path('inventory/<int:variant_id>/', SellerInventoryStockAPIView.as_view()),
    path('orders/update/<int:pk>/', OrderStatusUpdateAPIView.as_view()),
    path('kyc/', KYCAPIView.as_view()),
    path('bank/', BankAPIView.as_view()),
    path('payout/', PayoutAPIView.as_view()),
]
