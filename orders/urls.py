from django.urls import path
from .views import (
    CustomerOrderRequestView,
    CouponPreviewView,
    CheckoutView,
    CustomerOrderHistoryAPIView,
    SellerDashboardAPIView,
    OrderStatusUpdateAPIView,
    RazorpayWebhookAPIView,
    VerifyPaymentView,
)

urlpatterns = [
    path('coupon/preview/', CouponPreviewView.as_view()),
    path('customer/shipments/<int:pk>/requests/', CustomerOrderRequestView.as_view()),
    path('checkout/', CheckoutView.as_view()),
    path('payment/verify/', VerifyPaymentView.as_view()),
    path('razorpay/webhook/', RazorpayWebhookAPIView.as_view()),
    path('customer/history/', CustomerOrderHistoryAPIView.as_view()),
    path('seller/dashboard/', SellerDashboardAPIView.as_view()),
    path('update-status/<int:pk>/', OrderStatusUpdateAPIView.as_view()),
]
