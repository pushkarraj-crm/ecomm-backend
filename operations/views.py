from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
from decimal import Decimal
from django.contrib.auth import authenticate
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDate
from django.http import Http404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import BasePermission, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError, MethodNotAllowed
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User
from customers.models import SupportTicket
from products.models import Product, Category, StoreBanner, DeliveryArea, ProductVariant
from products.selectors import catalog_products
from orders.models import Order, SellerOrder, Payment, Refund, Coupon, CustomerOrderRequest
from orders.serializers import OrderSerializer
from sellers.models import Payout, KYC
from core.pagination import ProductPagination
from .serializers import (UserRead, SellerWrite, CustomerWrite, ProductRead, ProductWrite,
    CategoryWrite, BannerWrite, DeliveryWrite, CouponWrite, RequestWrite, SupportWrite, InventoryWrite)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and user.is_active and user.is_staff and user.is_superuser and not user.is_blacklisted)


class AdminView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = 'login'

    def post(self, request):
        class Credentials(serializers.Serializer):
            email = serializers.EmailField()
            password = serializers.CharField(max_length=256, trim_whitespace=False)
        credentials = Credentials(data=request.data)
        credentials.is_valid(raise_exception=True)
        user = authenticate(**credentials.validated_data)
        if not user or not user.is_staff or not user.is_superuser or not user.is_active or user.is_blacklisted:
            return Response({'error': 'Invalid administrator credentials.'}, status=401)
        refresh = RefreshToken.for_user(user)
        return Response({'access': str(refresh.access_token), 'refresh': str(refresh), 'email': user.email, 'is_superuser': True})


class MeView(AdminView):
    def get(self, request):
        return Response({'email': request.user.email, 'is_superuser': True})


class OverviewView(AdminView):
    def get(self, request):
        report_zone = ZoneInfo("Asia/Kolkata")
        today = timezone.localdate(timezone=report_zone)
        start = today - timedelta(days=6)
        paid = Order.objects.filter(status__in=['paid', 'partially_refunded', 'refunded'])
        gross = Decimal(str(paid.aggregate(total=Sum('total_amount'))['total'] or 0))
        refunds = Decimal(Refund.objects.filter(status='processed').aggregate(total=Sum('amount_paise'))['total'] or 0)/100
        daily = {row['day']: row for row in paid.filter(created_at__gte=datetime.combine(start, time.min, tzinfo=report_zone)).annotate(day=TruncDate('created_at', tzinfo=report_zone)).values('day').annotate(total=Sum('total_amount'), count=Count('id'))}
        chart = [{'day': start+timedelta(days=i), 'total': round(daily.get(start+timedelta(days=i),{}).get('total',0),2), 'count': daily.get(start+timedelta(days=i),{}).get('count',0)} for i in range(7)]
        return Response({'metrics': {
            'net_sales': round(gross-refunds,2), 'gross_sales': round(gross,2), 'processed_refunds': refunds,
            'paid_orders': paid.count(), 'sellers': User.objects.filter(is_seller=True, is_superuser=False).count(),
            'customers': User.objects.filter(is_customer=True, is_seller=False, is_staff=False).count(),
            'products': Product.objects.count(), 'pending_sellers': User.objects.filter(is_seller=True,seller_status='pending',is_superuser=False).count(),
            'pending_products': Product.objects.filter(status='pending').count(), 'open_support': SupportTicket.objects.filter(status='open').count(),
            'pending_requests': CustomerOrderRequest.objects.filter(status='pending').count(), 'low_stock': ProductVariant.objects.filter(stock__lte=5).count(),
            'pending_kyc': KYC.objects.filter(status='pending').count(), 'pending_payouts': Payout.objects.filter(status='pending').count(),
        }, 'sales': chart, 'recent_orders': OrderSerializer(Order.objects.select_related('payment').prefetch_related('seller_orders__items__product_variant__product','seller_orders__refunds','seller_orders__customer_requests').order_by('-id')[:6],many=True).data})


def resources():
    # Explicit allowlists: credentials, identity documents and bank details are never serialized here.
    return {
        'sellers': (User.objects.filter(is_seller=True,is_superuser=False).select_related('seller_profile','customer_profile'), UserRead, SellerWrite, ['email','seller_profile__store_name'], ['seller_status','is_blacklisted'], False),
        'customers': (User.objects.filter(is_customer=True,is_seller=False,is_staff=False,is_superuser=False).select_related('seller_profile','customer_profile'), UserRead, CustomerWrite, ['email','customer_profile__name'], ['is_active'], False),
        'products': (catalog_products(), ProductRead, ProductWrite, ['name','seller__email'], ['status','is_active'], False),
        'categories': (Category.objects.all(), CategoryWrite, CategoryWrite, ['name'], [], True),
        'banners': (StoreBanner.objects.all(), BannerWrite, BannerWrite, ['title'], ['is_active'], True),
        'delivery': (DeliveryArea.objects.all(), DeliveryWrite, DeliveryWrite, ['postal_code','city'], ['is_active'], True),
        'coupons': (Coupon.objects.all(), CouponWrite, CouponWrite, ['code','seller__email'], ['is_active'], True),
        'inventory': (ProductVariant.objects.select_related('product'), None, InventoryWrite, ['product__name'], [], False),
        'orders': (Order.objects.select_related('payment').prefetch_related('seller_orders__items__product_variant__product','seller_orders__refunds','seller_orders__customer_requests'), OrderSerializer, None, ['email','name'], ['status'], False),
        'requests': (CustomerOrderRequest.objects.select_related('seller_order__order'), None, RequestWrite, ['reason','seller_order__order__email'], ['status','kind'], False),
        'support': (SupportTicket.objects.select_related('user'), None, SupportWrite, ['subject','user__email'], ['status'], False),
        'refunds': (Refund.objects.all(), None, None, ['reason'], ['status'], False),
        'payouts': (Payout.objects.select_related('seller'), None, None, ['seller__store_name'], ['status'], False),
        'activity': (LogEntry.objects.select_related('user'), None, None, ['object_repr','user__email'], [], False),
    }


def record_data(resource, obj, serializer=None):
    if serializer:
        return serializer(obj).data
    if resource == 'inventory':
        return {'id':obj.id,'product_name':obj.product.name,'size':obj.size,'color':obj.color,'price':obj.price,'original_price':obj.original_price,'stock':obj.stock}
    if resource == 'requests':
        return {'id':obj.id,'order_id':obj.seller_order.order_id,'seller_order':obj.seller_order_id,'customer':obj.seller_order.order.email,'kind':obj.kind,'reason':obj.reason,'status':obj.status,'response':obj.response,'created_at':obj.created_at}
    if resource == 'support':
        return {'id':obj.id,'customer':obj.user.email,'subject':obj.subject,'message':obj.message,'status':obj.status,'response':obj.response,'created_at':obj.created_at}
    if resource == 'refunds':
        return {'id':obj.id,'seller_order':obj.seller_order_id,'amount':obj.amount_paise/100,'reason':obj.reason,'status':obj.status,'created_at':obj.created_at}
    if resource == 'payouts':
        return {'id':obj.id,'seller':obj.seller_id,'store_name':obj.seller.store_name or obj.seller.business_name,'amount':obj.amount,'status':obj.status,'created_at':obj.created_at}
    if resource == 'activity':
        return {'id':obj.id,'actor':obj.user.email,'record':obj.object_repr,'action':obj.get_action_flag_display(),'change':obj.change_message,'created_at':obj.action_time}
    raise Http404


class ResourceView(AdminView):
    def spec(self, resource):
        spec = resources().get(resource)
        if not spec:
            raise Http404
        return spec

    def get(self, request, resource, pk=None):
        queryset, read, write, search_fields, filter_fields, create = self.spec(resource)
        if pk is not None:
            obj = queryset.filter(pk=pk).first()
            if not obj:
                raise Http404
            return Response(record_data(resource,obj,read))
        search = request.query_params.get('search','').strip()
        if len(search)>100:
            raise ValidationError({'search':'Use at most 100 characters.'})
        if search:
            query = Q()
            for field in search_fields:
                query |= Q(**{field+'__icontains':search})
            if search.isdigit():
                query |= Q(pk=int(search))
            queryset = queryset.filter(query)
        for field in filter_fields:
            value=request.query_params.get(field)
            if value is not None and value != '':
                if field.startswith('is_'):
                    if value not in ('true','false'):
                        raise ValidationError({field:'Use true or false.'})
                    value=value=='true'
                queryset=queryset.filter(**{field:value})
        pager=ProductPagination()
        page=pager.paginate_queryset(queryset.order_by('-pk'),request,view=self)
        return pager.get_paginated_response([record_data(resource,obj,read) for obj in page])

    @transaction.atomic
    def post(self, request, resource, pk=None):
        queryset, read, write, search, filters, create = self.spec(resource)
        if not create or pk is not None:
            raise MethodNotAllowed('POST')
        return self.save(request,resource,read,write,None)

    @transaction.atomic
    def patch(self, request, resource, pk):
        queryset, read, write, search, filters, create = self.spec(resource)
        if not write:
            raise MethodNotAllowed('PATCH')
        obj=queryset.select_for_update(of=('self',)).filter(pk=pk).first()
        if not obj:
            raise Http404
        return self.save(request,resource,read,write,obj)

    def save(self,request,resource,read,write,obj):
        allowed={key for key,field in write().fields.items() if not field.read_only}
        unknown=set(request.data)-allowed
        if unknown:
            raise ValidationError({key:'This field cannot be edited here.' for key in unknown})
        if not request.data:
            raise ValidationError('Provide at least one editable field.')
        serializer=write(obj,data=request.data,partial=obj is not None)
        serializer.is_valid(raise_exception=True)
        instance=serializer.save()
        LogEntry.objects.log_action(user_id=request.user.pk,content_type_id=ContentType.objects.get_for_model(instance).pk,
            object_id=str(instance.pk),object_repr=str(instance)[:200],action_flag=CHANGE if obj else ADDITION,
            change_message='Updated fields: '+', '.join(sorted(serializer.validated_data)))
        # Refresh annotated catalog data after approval changes.
        if resource=='products':
            instance=catalog_products().get(pk=instance.pk)
        return Response(record_data(resource,instance,read),status=200 if obj else 201)
