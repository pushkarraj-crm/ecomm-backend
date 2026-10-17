from decimal import Decimal
from rest_framework import serializers


class CatalogDetailsSerializer(serializers.Serializer):
    gst_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
    )
    hsn_code = serializers.RegexField(r"^\d{4,8}$", required=False)
    net_weight_g = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001"), required=False
    )
    net_quantity = serializers.IntegerField(
        min_value=1, max_value=100000, required=False
    )
    style_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    generic_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    material = serializers.CharField(max_length=100, required=False, allow_blank=True)
    cover_fabric = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    filling = serializers.CharField(max_length=100, required=False, allow_blank=True)
    pattern = serializers.CharField(max_length=100, required=False, allow_blank=True)
    secondary_color = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    product_type = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    dimension_unit = serializers.ChoiceField(
        choices=["cm", "mm", "in", "m"], required=False
    )
    length = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001"), required=False
    )
    width = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001"), required=False
    )
    height = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001"), required=False
    )
    country_of_origin = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    manufacturer_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    manufacturer_address = serializers.CharField(
        max_length=1000, required=False, allow_blank=True
    )
    manufacturer_postal_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    packer_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    packer_address = serializers.CharField(
        max_length=1000, required=False, allow_blank=True
    )
    packer_postal_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    importer_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    importer_address = serializers.CharField(
        max_length=1000, required=False, allow_blank=True
    )
    importer_postal_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True
    )
    brand = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {key: "Unknown catalog detail." for key in unknown}
                )
        values = super().to_internal_value(data)
        return {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in values.items()
        }

    def validate(self, attrs):
        if any(
            name in attrs for name in ["length", "width", "height"]
        ) and not attrs.get("dimension_unit"):
            raise serializers.ValidationError(
                {"dimension_unit": "Choose a unit for product dimensions."}
            )
        return attrs
