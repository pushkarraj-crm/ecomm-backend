import json
import hashlib

from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle

from accounts.permissions import IsApprovedSeller

from .services import ProductService, ReviewService
from .selectors import (
    PRODUCT_SORT_OPTIONS,
    get_all_products,
    get_category_tree,
    get_product_detail,
)
from .models import Product, ProductInteraction
from .serializers import (
    ProductReadSerializer,
    ProductWriteSerializer,
    ProductImageUploadSerializer,
    ReviewWriteSerializer,
)
from core.pagination import ProductPagination


# =========================
# CREATE PRODUCT
# =========================
class CreateProductView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedSeller]

    def post(self, request):
        data = request.data
        variants = data.get('variants')
        if isinstance(variants, str):
            try:
                variants = json.loads(variants)
            except (TypeError, ValueError):
                variants = None
            data = data.dict() if hasattr(data, 'dict') else dict(data)
            data['variants'] = variants

        serializer = ProductWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        images_by_variant = []
        for index, _ in enumerate(serializer.validated_data['variants']):
            validated_images = []
            for image in request.FILES.getlist(f"variant_{index}_images"):
                image_serializer = ProductImageUploadSerializer(data={'image': image})
                image_serializer.is_valid(raise_exception=True)
                validated_images.append(image_serializer.validated_data['image'])
            images_by_variant.append(validated_images)

        ProductService.create_product_with_variants(
            request.user,
            serializer.validated_data,
            images_by_variant,
        )

        return Response({"msg": "Product created"})


# =========================
# PRODUCT LIST
# =========================
class ProductListView(APIView):

    def get(self, request):
        search = request.query_params.get('search')
        if search is None:
            search = request.query_params.get('q', '')
        search = search.strip()
        if len(search) > 100:
            raise ValidationError({'search': 'Search must be 100 characters or fewer.'})

        sort = (
            request.query_params.get('sort')
            or request.query_params.get('sort_by')
            or ''
        ).strip().lower()
        if sort and sort not in PRODUCT_SORT_OPTIONS:
            valid_options = ', '.join(sorted(PRODUCT_SORT_OPTIONS))
            raise ValidationError({'sort': f'Choose one of: {valid_options}.'})

        has_catalog_options = bool(search or sort)
        use_pagination = (
            'page' in request.query_params
            or 'page_size' in request.query_params
            or has_catalog_options
        )
        if request.query_params or use_pagination:
            cache_key = 'catalog:list:query:' + hashlib.sha256(
                request.get_full_path().encode('utf-8')
            ).hexdigest()
        else:
            cache_key = 'catalog:list:all:v1'

        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        products = get_all_products(search=search or None, sort=sort or None)
        if use_pagination:
            paginator = ProductPagination()
            page = paginator.paginate_queryset(products, request, view=self)
            serializer = ProductReadSerializer(page, many=True)
            response_data = paginator.get_paginated_response(serializer.data).data
        else:
            serializer = ProductReadSerializer(products, many=True)
            response_data = serializer.data

        cache.set(cache_key, response_data, settings.PRODUCT_CACHE_TTL_SECONDS)
        return Response(response_data)


# =========================
# PRODUCT DETAIL
# =========================
class ProductDetailView(APIView):

    def get(self, request, product_id):
        cache_key = f'catalog:detail:v1:{product_id}'
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        product = get_product_detail(product_id)

        if not product:
            return Response({"error": "Not found"}, status=404)

        serializer = ProductReadSerializer(product)
        cache.set(cache_key, serializer.data, settings.PRODUCT_CACHE_TTL_SECONDS)
        return Response(serializer.data)


class CategoryListView(APIView):
    """Return the nested category data used by the seller catalog picker."""

    def get(self, request):
        search = request.query_params.get('search', '').strip()
        if len(search) > 100:
            raise ValidationError({'search': 'Search must be 100 characters or fewer.'})
        cache_key = 'catalog:categories:v1:' + hashlib.sha256(
            search.casefold().encode('utf-8')
        ).hexdigest()
        categories = cache.get(cache_key)
        if categories is None:
            categories = get_category_tree(search=search or None)
            cache.set(cache_key, categories, max(settings.PRODUCT_CACHE_TTL_SECONDS, 60))
        return Response(categories)


class TrackProductInteractionView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'product_tracking'

    def post(self, request, product_id):
        event = request.data.get('event') if hasattr(request.data, 'get') else None
        if not isinstance(event, str) or event not in {'view', 'click'}:
            raise ValidationError({'event': 'Choose either view or click.'})
        product = Product.objects.filter(
            id=product_id,
            is_active=True,
            status='approved',
        ).only('id').first()
        if product is None:
            raise Http404
        ProductInteraction.objects.create(product_id=product_id, event=event)
        return Response({'tracked': True}, status=202)


# =========================
# ADD REVIEW
# =========================
class AddReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ReviewService.add_review(
            user=request.user,
            product=serializer.validated_data['product'],
            rating=serializer.validated_data['rating'],
            comment=serializer.validated_data['comment'],
        )

        return Response({"msg": "Review added"})
