"""Owner-scoped seller catalog management; public approval stays admin-controlled."""
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsSeller
from core.pagination import ProductPagination
from products.models import Category, Product
from products.selectors import catalog_products, category_descendant_ids
from products.serializers import ProductReadSerializer


class SellerCatalogReadSerializer(ProductReadSerializer):
    class Meta(ProductReadSerializer.Meta):
        fields = ProductReadSerializer.Meta.fields + ['status', 'is_active', 'created_at', 'updated_at']


class SellerCatalogQuerySerializer(serializers.Serializer):
    search = serializers.CharField(max_length=100, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Product.STATUS_CHOICES, required=False)
    category = serializers.IntegerField(min_value=1, required=False)
    is_active = serializers.BooleanField(required=False)


class SellerCatalogUpdateSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False)

    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'is_active', 'return_policy', 'return_days']
        extra_kwargs = {'name': {'required': False}, 'description': {'required': False}}

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Provide at least one editable field.')
        policy = attrs.get('return_policy', self.instance.return_policy)
        days = attrs.get('return_days', self.instance.return_days)
        if policy == 'no_return':
            if attrs.get('return_days') is not None:
                raise serializers.ValidationError({'return_days': 'Leave empty for no_return.'})
            attrs['return_days'] = None
        elif days is None:
            raise serializers.ValidationError({'return_days': 'Choose 2, 5, or 7 days.'})
        return attrs


class SellerCatalogAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        query = SellerCatalogQuerySerializer(data=request.query_params.dict())
        query.is_valid(raise_exception=True)
        filters = query.validated_data
        products = catalog_products().filter(seller=request.user)
        for key in ('status', 'is_active'):
            if key in filters:
                products = products.filter(**{key: filters[key]})
        if filters.get('search'):
            products = products.filter(Q(name__icontains=filters['search']) | Q(slug__icontains=filters['search']))
        if 'category' in filters:
            products = products.filter(category_id__in=category_descendant_ids(filters['category']))
        paginator = ProductPagination()
        page = paginator.paginate_queryset(products.order_by('-created_at', '-id'), request, view=self)
        return paginator.get_paginated_response(SellerCatalogReadSerializer(page, many=True).data)


class SellerCatalogSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        return Response(Product.objects.filter(seller=request.user).aggregate(
            total=Count('id'), approved=Count('id', filter=Q(status='approved')),
            pending=Count('id', filter=Q(status='pending')), rejected=Count('id', filter=Q(status='rejected')),
            active=Count('id', filter=Q(is_active=True)), inactive=Count('id', filter=Q(is_active=False)),
        ))


class SellerCatalogDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request, product_id):
        product = catalog_products().filter(pk=product_id, seller=request.user).first()
        if product is None:
            raise Http404
        return Response(SellerCatalogReadSerializer(product).data)

    @transaction.atomic
    def patch(self, request, product_id):
        product = Product.objects.select_for_update().filter(pk=product_id, seller=request.user).first()
        if product is None:
            raise Http404
        serializer = SellerCatalogUpdateSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changed_content = any(getattr(product, key) != value for key, value in serializer.validated_data.items() if key != 'is_active')
        # Sellers may pause listings, but cannot self-approve modified content.
        serializer.save(**({'status': 'pending'} if changed_content else {}))
        updated = catalog_products().get(pk=product.pk)
        return Response(SellerCatalogReadSerializer(updated).data)
