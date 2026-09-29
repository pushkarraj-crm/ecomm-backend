from django.urls import path
from .views import (
    GetCartView,
    UpdateCartItemView,
    RemoveCartItemView,
    ClearCartView
)

urlpatterns = [
    path('', GetCartView.as_view()),
    path('update/<int:item_id>/', UpdateCartItemView.as_view()),
    path('remove/<int:item_id>/', RemoveCartItemView.as_view()),
    path('clear/', ClearCartView.as_view()),
]
