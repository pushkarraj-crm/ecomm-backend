from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from accounts.permissions import IsSeller
from products.serializers import ProductImageUploadSerializer
from products.image_quality import check_catalog_image


class SellerImageCheckView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]
    throttle_scope = "image_check"

    def post(self, request):
        if int(request.META.get("CONTENT_LENGTH") or 0) > 20 * 1024 * 1024:
            raise ValidationError("Upload at most 20 MB of images at a time.")
        images = request.FILES.getlist("images")
        if not 1 <= len(images) <= 9:
            raise ValidationError({"images": "Choose between 1 and 9 images."})
        results = []
        for index, image in enumerate(images):
            serializer = ProductImageUploadSerializer(data={"image": image})
            if not serializer.is_valid():
                results.append(
                    {
                        "index": index,
                        "name": image.name,
                        "status": "rejected",
                        "reasons": [
                            str(reason)
                            for reasons in serializer.errors.values()
                            for reason in reasons
                        ],
                    }
                )
                continue
            try:
                checks = check_catalog_image(serializer.validated_data["image"])
                results.append(
                    {
                        "index": index,
                        "name": image.name,
                        "status": "pending_review",
                        "reasons": [],
                        "checks": checks,
                    }
                )
            except ValidationError as error:
                results.append(
                    {
                        "index": index,
                        "name": image.name,
                        "status": "rejected",
                        "reasons": [str(reason) for reason in error.detail],
                    }
                )
        return Response(
            {
                "results": results,
                "review_note": "Technical checks do not replace admin review of branding, watermarks or image content.",
            }
        )
