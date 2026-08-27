from rest_framework import serializers
from .models import APIKey

class APIKeySerializer(serializers.ModelSerializer):
    key = serializers.UUIDField(read_only=True)

    class Meta:
        model  = APIKey
        fields = ['id', 'name', 'key', 'tier', 'is_active', 'created_at']
        read_only_fields = ['id', 'key', 'tier', 'is_active', 'created_at']