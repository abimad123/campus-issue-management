from django.urls import reverse
from rest_framework import serializers

from .models import Asset


class AssetSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.display_name", read_only=True)
    qr_endpoint = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = ("id", "asset_code", "name", "asset_type", "location", "location_name", "qr_identifier", "qr_endpoint", "is_active", "created_at", "updated_at")
        read_only_fields = ("qr_identifier", "created_at", "updated_at")

    def get_qr_endpoint(self, obj):
        path = reverse("asset-qr", kwargs={"pk": obj.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path
