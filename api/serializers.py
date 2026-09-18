from rest_framework import serializers
from django.utils import timezone

from .models import APIKey

class APIKeySerializer(serializers.ModelSerializer):
    masked_key = serializers.CharField(read_only=True)
    tier = serializers.CharField(read_only=True)
    is_usable = serializers.BooleanField(read_only=True)

    def validate_scopes(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("Choose at least one scope.")
        scopes = list(dict.fromkeys(str(item).strip().lower() for item in value))
        invalid = set(scopes) - APIKey.ALLOWED_SCOPES
        if invalid:
            raise serializers.ValidationError(f"Unsupported scopes: {', '.join(sorted(invalid))}.")
        return scopes

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiry must be in the future.")
        return value

    class Meta:
        model = APIKey
        fields = [
            'id', 'name', 'masked_key', 'prefix', 'tier', 'scopes', 'is_active',
            'is_usable', 'created_at', 'last_used_at', 'expires_at', 'revoked_at',
        ]
        read_only_fields = [
            'id', 'masked_key', 'prefix', 'tier', 'is_active', 'is_usable',
            'created_at', 'last_used_at', 'revoked_at',
        ]
