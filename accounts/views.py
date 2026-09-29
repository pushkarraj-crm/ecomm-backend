from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import (
    CustomerRegisterSerializer,
    CustomerLoginSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    ResetPasswordSerializer,
    SellerLoginSerializer,
    SellerRegisterSerializer,
)
from .services import UserService


class RegisterCustomerView(APIView):
    throttle_scope = 'register'

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"msg": "Customer registered"})


class RegisterSellerView(APIView):
    throttle_scope = 'register'

    def post(self, request):
        serializer = SellerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"msg": "Seller registered, pending approval"})


class LoginView(APIView):
    throttle_scope = 'login'
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response({"error": "Invalid credentials"}, status=400)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "is_seller": user.is_seller,
            "seller_status": user.seller_status
        })


class CustomerLoginView(LoginView):
    serializer_class = CustomerLoginSerializer


class SellerLoginView(LoginView):
    serializer_class = SellerLoginSerializer


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_url = request.build_absolute_uri(reverse('password-reset'))
        UserService.request_password_reset(
            email=serializer.validated_data['email'],
            reset_url=reset_url,
        )
        return Response(
            {'message': 'If an account exists for that email, password reset instructions have been sent.'},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Password reset successfully.'})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        UserService.logout(serializer.validated_data['refresh'])
        return Response({'message': 'Logged out successfully.'})
