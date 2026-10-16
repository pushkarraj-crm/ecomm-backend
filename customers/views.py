from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import Http404

from accounts.permissions import IsCustomer
from .serializers import (
    AddToCartSerializer,
    CustomerAddressInputSerializer,
    CustomerAddressSerializer,
    CustomerProfileInputSerializer,
    CustomerProfileSerializer,
)
from .selectors import get_customer_address, get_customer_profile
from .services import (
    add_to_cart,
    create_customer_address,
    delete_customer_address,
    save_customer_profile,
    update_customer_address,
)


class CustomerProfileView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        profile = get_customer_profile(request.user)
        if profile is None:
            raise Http404
        return Response(CustomerProfileSerializer(profile).data)

    def post(self, request):
        serializer = CustomerProfileInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile, created = save_customer_profile(request.user, serializer.validated_data)
        return Response(
            CustomerProfileSerializer(profile).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def patch(self, request):
        profile = get_customer_profile(request.user)
        if profile is None:
            raise Http404
        serializer = CustomerProfileInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        profile, _ = save_customer_profile(request.user, serializer.validated_data)
        return Response(CustomerProfileSerializer(profile).data)


class CustomerAddressListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        profile = get_customer_profile(request.user)
        if profile is None:
            raise Http404
        addresses = profile.addresses.all()
        return Response(CustomerAddressSerializer(addresses, many=True).data)

    def post(self, request):
        profile = get_customer_profile(request.user)
        if profile is None:
            raise Http404
        serializer = CustomerAddressInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        address = create_customer_address(profile, serializer.validated_data)
        return Response(
            CustomerAddressSerializer(address).data,
            status=status.HTTP_201_CREATED,
        )


class CustomerAddressDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def patch(self, request, address_id):
        address = get_customer_address(request.user, address_id)
        if address is None:
            raise Http404
        serializer = CustomerAddressInputSerializer(
            address,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        address = update_customer_address(address, serializer.validated_data)
        return Response(CustomerAddressSerializer(address).data)

    def delete(self, request, address_id):
        address = get_customer_address(request.user, address_id)
        if address is None:
            raise Http404
        delete_customer_address(address)
        return Response({'message': 'Address removed'})


class AddToCartView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart, item = add_to_cart(
            user=request.user,
            product_variant=serializer.validated_data['product_variant'],
            quantity=serializer.validated_data['quantity'],
        )

        return Response(
            {
                'message': 'Item added to cart',
                'cart_id': cart.id,
                'item_id': item.id,
                'variant_id': item.product_variant_id,
                'quantity': item.quantity,
            },
            status=status.HTTP_200_OK,
        )


class SupportTicketView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        from .models import SupportTicket
        return Response(list(SupportTicket.objects.filter(user=request.user).order_by('-id').values('id','subject','message','status','response','created_at')[:50]))

    def post(self, request):
        from rest_framework import serializers
        from .models import SupportTicket
        class TicketInput(serializers.Serializer):
            subject = serializers.CharField(max_length=150, min_length=5)
            message = serializers.CharField(max_length=4000, min_length=10)
        serializer=TicketInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket=SupportTicket.objects.create(user=request.user, **serializer.validated_data)
        return Response({'id':ticket.id,'status':ticket.status}, status=201)
