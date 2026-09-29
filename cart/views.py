from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import Http404

from .serializers import CartItemUpdateSerializer, CartSerializer
from .selectors import get_cart_for_user, get_cart_item_for_user
from .services import (
    clear_cart,
    get_or_create_cart,
    remove_cart_item,
    update_cart_item,
)


# ✅ Get Cart
class GetCartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart = get_or_create_cart(request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)


# ✅ Update Cart Item
class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        item = get_cart_item_for_user(request.user, item_id)
        if item is None:
            raise Http404

        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_cart_item(item, serializer.validated_data['quantity'])

        return Response({"message": "Cart updated"})


# ✅ Remove Item
class RemoveCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        item = get_cart_item_for_user(request.user, item_id)
        if item is None:
            raise Http404
        remove_cart_item(item)
        return Response({"message": "Item removed"})


# ✅ Clear Cart
class ClearCartView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        cart = get_cart_for_user(request.user)
        if cart is None:
            raise Http404
        clear_cart(cart)
        return Response({"message": "Cart cleared"})
