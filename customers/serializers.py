from rest_framework import serializers

from products.models import ProductVariant
from .models import CustomerAddress, CustomerProfile


class AddToCartSerializer(serializers.Serializer):
    variant_id = serializers.PrimaryKeyRelatedField(
        source='product_variant',
        queryset=ProductVariant.objects.all(),
    )
    quantity = serializers.IntegerField(default=1, min_value=1)


class CustomerAddressInputSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=50, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    address_line_1 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    landmark = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, default='India')
    is_default = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        existing = {}
        if self.partial and self.instance is not None:
            existing = {
                field: getattr(self.instance, field)
                for field in (
                    'address', 'address_line_1', 'address_line_2', 'landmark',
                    'city', 'state', 'postal_code', 'country',
                )
            }
        merged = {**existing, **attrs}
        structured_fields = ('address_line_1', 'city', 'state', 'postal_code')
        structured_address = any(merged.get(field) for field in structured_fields)

        if structured_address:
            missing = [field for field in structured_fields if not merged.get(field)]
            if missing:
                raise serializers.ValidationError({
                    field: 'This field is required for a structured delivery address.'
                    for field in missing
                })
            structured_fields_changed = any(
                field in attrs
                for field in (
                    'address_line_1', 'address_line_2', 'landmark',
                    'city', 'state', 'postal_code', 'country',
                )
            )
            if not merged.get('address') or structured_fields_changed:
                parts = [
                    merged.get('address_line_1'), merged.get('address_line_2'),
                    merged.get('landmark'), merged.get('city'), merged.get('state'),
                    merged.get('postal_code'), merged.get('country') or 'India',
                ]
                attrs['address'] = ', '.join(part for part in parts if part)
            attrs.setdefault('country', merged.get('country') or 'India')
        elif not merged.get('address'):
            raise serializers.ValidationError({
                'address': 'Provide a legacy address string or a complete structured address.'
            })

        return attrs


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = [
            'id', 'label', 'address', 'address_line_1', 'address_line_2',
            'landmark', 'city', 'state', 'postal_code', 'country',
            'is_default', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CustomerProfileSerializer(serializers.ModelSerializer):
    addresses = CustomerAddressSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ['id', 'name', 'mobile_number', 'addresses', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class CustomerProfileInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    mobile_number = serializers.CharField(max_length=20)
    addresses = CustomerAddressInputSerializer(many=True, required=True, allow_empty=False)

    def validate_addresses(self, addresses):
        if sum(address.get('is_default', False) for address in addresses) > 1:
            raise serializers.ValidationError('Only one address can be the default.')
        return addresses
