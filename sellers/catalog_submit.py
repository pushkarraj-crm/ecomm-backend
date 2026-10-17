"""Atomic, retry-safe submission of a single-category seller catalog."""

import json
import logging
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsApprovedSeller
from products.models import Product
from products.serializers import ProductWriteSerializer, ProductImageUploadSerializer
from products.services import ProductService
from .models import SellerCatalogSubmission


class CatalogSubmissionInput(serializers.Serializer):
    submission_id = serializers.UUIDField()
    products = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=9
    )


class SellerCatalogSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedSeller]

    def post(self, request):
        if int(request.META.get("CONTENT_LENGTH") or 0) > 50 * 1024 * 1024:
            raise ValidationError(
                "Catalog uploads must be smaller than 50 MB in total."
            )
        raw = request.data.get("products")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                raise ValidationError({"products": "Provide a valid product list."})
        payload = CatalogSubmissionInput(
            data={"submission_id": request.data.get("submission_id"), "products": raw}
        )
        payload.is_valid(raise_exception=True)
        validated = []
        errors = {}
        category_ids = set()
        for index, product in enumerate(payload.validated_data["products"]):
            unknown = set(product) - set(ProductWriteSerializer().fields)
            if unknown:
                errors[index] = {
                    key: "This field cannot be submitted here." for key in unknown
                }
                continue
            serializer = ProductWriteSerializer(data=product)
            if not serializer.is_valid():
                errors[index] = serializer.errors
                continue
            values = serializer.validated_data
            category = values["category"]
            if category.subcategories.exists():
                errors[index] = {
                    "category": "Choose the final category in the hierarchy."
                }
                continue
            category_ids.add(category.pk)
            files = request.FILES.getlist(f"product_{index}_images")
            if not 1 <= len(files) <= 8:
                errors[index] = {"images": "Upload between 1 and 8 images per product."}
                continue
            images = []
            for image in files:
                upload = ProductImageUploadSerializer(
                    data={"image": image}, context={"catalog_quality": True}
                )
                if not upload.is_valid():
                    errors[index] = {"images": upload.errors}
                    break
                images.append(upload.validated_data["image"])
            validated.append((values, images))
        if errors:
            raise ValidationError({"products": errors})
        if len(category_ids) != 1:
            raise ValidationError(
                {
                    "products": "All products in one catalog must use the same final category."
                }
            )
        uploaded_files = []
        try:
            with transaction.atomic():
                (
                    submission,
                    _,
                ) = SellerCatalogSubmission.objects.select_for_update().get_or_create(
                    id=payload.validated_data["submission_id"],
                    defaults={"seller": request.user},
                )
                if submission.seller_id != request.user.pk:
                    raise PermissionDenied("This submission belongs to another seller.")
                if submission.product_ids:
                    return Response(
                        {
                            "message": "Catalog already submitted.",
                            "product_ids": submission.product_ids,
                            "count": len(submission.product_ids),
                        },
                        status=200,
                    )
                products = []
                for values, images in validated:
                    image_groups = [images] + [[] for _ in values["variants"][1:]]
                    products.append(
                        ProductService.create_product_with_variants(
                            request.user,
                            values,
                            image_groups,
                            uploaded_files=uploaded_files,
                            require_image_review=True,
                        )
                    )
                submission.product_ids = [product.pk for product in products]
                submission.save(update_fields=["product_ids"])
                result = {
                    "message": "Catalog submitted for approval.",
                    "product_ids": submission.product_ids,
                    "count": len(products),
                }
        except Exception:
            for stored in uploaded_files:
                try:
                    stored.storage.delete(stored.name)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Could not remove an upload after a failed catalog submission."
                    )
            raise
        return Response(result, status=201)
