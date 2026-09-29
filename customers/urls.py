from django.urls import path

from .views import (
    AddToCartView,
    CustomerAddressDetailView,
    CustomerAddressListCreateView,
    CustomerProfileView,
)


urlpatterns = [
    path('profile/', CustomerProfileView.as_view(), name='customer-profile'),
    path('addresses/', CustomerAddressListCreateView.as_view(), name='customer-addresses'),
    path(
        'addresses/<int:address_id>/',
        CustomerAddressDetailView.as_view(),
        name='customer-address-detail',
    ),
    path('cart/add/', AddToCartView.as_view(), name='customer-add-to-cart'),
]
