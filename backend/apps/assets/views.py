import qrcode
from django.http import HttpResponse
from django.urls import path
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.users.permissions import IsCampusAdministrator

from .models import Asset
from .serializers import AssetSerializer


class AssetViewSet(viewsets.ModelViewSet):
    serializer_class = AssetSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        return [IsCampusAdministrator()]

    def get_queryset(self):
        return Asset.objects.filter(is_active=True).select_related("location__building")

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated], url_path="qr", url_name="qr")
    def qr(self, request, pk=None):
        asset = self.get_object()
        qr_image = qrcode.make(f"campus-asset:{asset.qr_identifier}")
        response = HttpResponse(content_type="image/png")
        qr_image.save(response, format="PNG")
        response["Content-Disposition"] = f'inline; filename="{asset.asset_code}-qr.png"'
        return response
