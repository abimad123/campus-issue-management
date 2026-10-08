from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.services import record_audit
from apps.issues.serializers import IssueCreateSerializer, IssueDetailSerializer
from .filters import NetworkDeviceFilter, NetworkFilter, NetworkMeasurementFilter
from .models import Network, NetworkDevice, NetworkMeasurement
from .permissions import CanManageNetworkInventory, CanReadNetworkOperations
from .serializers import NetworkDeviceSerializer, NetworkMeasurementSerializer, NetworkSerializer
from .services import attach_network_context, evaluate_measurement


class NetworkViewSet(viewsets.ModelViewSet):
    queryset = Network.objects.select_related("campus", "building")
    serializer_class = NetworkSerializer
    permission_classes = [CanManageNetworkInventory]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = NetworkFilter
    search_fields = ["name", "code", "campus__name", "building__name"]
    ordering_fields = ["name", "code", "kind", "created_at"]
    ordering = ["campus__name", "name"]
    audit_entity = "network"

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            record_audit(f"{self.audit_entity}.created", actor=self.request.user, entity=instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            record_audit(f"{self.audit_entity}.updated", actor=self.request.user, entity=instance)

    def perform_destroy(self, instance):
        with transaction.atomic():
            record_audit(f"{self.audit_entity}.deleted", actor=self.request.user, entity=instance)
            instance.delete()


class NetworkDeviceViewSet(viewsets.ModelViewSet):
    queryset = NetworkDevice.objects.select_related("network__campus", "network__building", "location__building", "asset")
    serializer_class = NetworkDeviceSerializer
    permission_classes = [CanManageNetworkInventory]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = NetworkDeviceFilter
    search_fields = ["device_code", "name", "manufacturer", "model_number", "network__name", "location__name", "location__building__name"]
    ordering_fields = ["device_code", "name", "kind", "state", "created_at"]
    ordering = ["device_code"]
    audit_entity = "network_device"

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            record_audit(f"{self.audit_entity}.created", actor=self.request.user, entity=instance)

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            record_audit(f"{self.audit_entity}.updated", actor=self.request.user, entity=instance)

    def perform_destroy(self, instance):
        with transaction.atomic():
            record_audit(f"{self.audit_entity}.deleted", actor=self.request.user, entity=instance)
            instance.delete()


class NetworkMeasurementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = NetworkMeasurement.objects.select_related("network", "location__building", "device", "recorded_by")
    serializer_class = NetworkMeasurementSerializer
    permission_classes = [CanReadNetworkOperations]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = NetworkMeasurementFilter
    ordering_fields = ["measured_at", "latency_ms", "packet_loss_percent", "download_mbps", "upload_mbps"]
    ordering = ["-measured_at", "-pk"]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    @action(detail=True, methods=["get"], url_path="evaluation")
    def evaluation(self, request, pk=None):
        measurement = self.get_object()
        return Response(evaluate_measurement(measurement))

    @action(detail=True, methods=["post"], url_path="create-issue")
    @transaction.atomic
    def create_issue(self, request, pk=None):
        measurement = self.get_object()
        issue_input = IssueCreateSerializer(data=request.data, context={"request": request})
        issue_input.is_valid(raise_exception=True)
        issue = issue_input.save()
        attach_network_context(issue=issue, measurement=measurement, actor=request.user)
        result = IssueDetailSerializer(issue, context={"request": request})
        return Response(result.data, status=status.HTTP_201_CREATED)
