from django.urls import path
from .views import (
    ForgotPasswordView,
    CustomerLoginView,
    LoginView,
    LogoutView,
    RegisterCustomerView,
    RegisterSellerView,
    ResetPasswordView,
    SellerLoginView,
)

urlpatterns = [
    path('register/', RegisterCustomerView.as_view()),
    path('seller/register/', RegisterSellerView.as_view()),
    path('customer/login/', CustomerLoginView.as_view()),
    path('seller/login/', SellerLoginView.as_view()),
    path('login/', LoginView.as_view()),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='password-reset'),
    path('logout/', LogoutView.as_view()),
]
