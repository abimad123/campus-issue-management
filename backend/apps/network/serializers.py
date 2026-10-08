from rest_framework import serializers

from .models import IssueNetworkContext, Network, NetworkDevice, NetworkMeasurement
from .services import evaluate_measurement


class NetworkSerializer(serializers.ModelSerializer):
    campus_name = serializers.CharField(source="campus.name", read_only=True)
    building_name = serializers.CharField(source="building.name", read_only=True, allow_null=True)

    class Meta:
        model = Network
        fields = ("id", "campus", "campus_name", "building", "building_name", "code", "name", "kind", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def validate(self, attrs):
        campus = attrs.get("campus", getattr(self.instance, "campus", None))
        building = attrs.get("building", getattr(self.instance, "building", None))
        if building and campus and building.campus_id != campus.pk:
            raise serializers.ValidationError({"building": "Choose a building in the selected campus."})
        return attrs


class NetworkDeviceSerializer(serializers.ModelSerializer):
    network_name = serializers.CharField(source="network.name", read_only=True)
    network_code = serializers.CharField(source="network.code", read_only=True)
    location_name = serializers.CharField(source="location.display_name", read_only=True)
    asset_code = serializers.CharField(source="asset.asset_code", read_only=True, allow_null=True)
    campus_name = serializers.CharField(source="network.campus.name", read_only=True)

    class Meta:
        model = NetworkDevice
        fields = ("id", "device_code", "name", "kind", "network", "network_name", "network_code", "campus_name", "location", "location_name", "asset", "asset_code", "manufacturer", "model_number", "serial_number", "state", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def validate(self, attrs):
        network = attrs.get("network", getattr(self.instance, "network", None))
        location = attrs.get("location", getattr(self.instance, "location", None))
        asset = attrs.get("asset", getattr(self.instance, "asset", None))
        if network and location and location.building_id:
            if location.building.campus_id != network.campus_id:
                raise serializers.ValidationError({"location": "Choose a location in the network's campus."})
            if network.building_id and location.building_id != network.building_id:
                raise serializers.ValidationError({"location": "Choose a location in the network's building."})
        if asset and location and asset.location_id != location.pk:
            raise serializers.ValidationError({"asset": "The linked asset must have the same campus location as this device."})
        return attrs


class NetworkMeasurementSerializer(serializers.ModelSerializer):
    network_name = serializers.CharField(source="network.name", read_only=True)
    location_name = serializers.CharField(source="location.display_name", read_only=True)
    device_code = serializers.CharField(source="device.device_code", read_only=True, allow_null=True)
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True)
    quality_evaluation = serializers.SerializerMethodField()

    def get_quality_evaluation(self, obj):
        return evaluate_measurement(obj)

    class Meta:
        model = NetworkMeasurement
        fields = ("id", "network", "network_name", "location", "location_name", "device", "device_code", "recorded_by", "recorded_by_name", "measured_at", "latency_ms", "packet_loss_percent", "download_mbps", "upload_mbps", "signal_strength_dbm", "connection_state", "note", "quality_evaluation")
        read_only_fields = ("recorded_by", "measured_at")

    def validate(self, attrs):
        network = attrs.get("network")
        location = attrs.get("location")
        device = attrs.get("device")
        if network and location and location.building_id:
            if location.building.campus_id != network.campus_id:
                raise serializers.ValidationError({"location": "Choose a location in the network's campus."})
            if network.building_id and location.building_id != network.building_id:
                raise serializers.ValidationError({"location": "Choose a location in the network's building."})
        if device:
            if network and device.network_id != network.pk:
                raise serializers.ValidationError({"device": "Choose a device connected to the selected network."})
            if location and device.location_id != location.pk:
                raise serializers.ValidationError({"location": "The selected device is registered at a different location."})
        metric_fields = ("latency_ms", "packet_loss_percent", "download_mbps", "upload_mbps", "signal_strength_dbm")
        if not any(attrs.get(field) is not None for field in metric_fields):
            raise serializers.ValidationError({"non_field_errors": "Enter at least one measured network value."})
        return attrs


class IssueNetworkContextCreateSerializer(serializers.Serializer):
    network_measurement = serializers.PrimaryKeyRelatedField(queryset=NetworkMeasurement.objects.all())


class IssueNetworkContextSerializer(serializers.ModelSerializer):
    measurement_id = serializers.IntegerField(source="network_measurement_id", read_only=True)
    measured_at = serializers.DateTimeField(source="network_measurement.measured_at", read_only=True)
    network_name = serializers.CharField(source="network_measurement.network.name", read_only=True)
    network_kind = serializers.CharField(source="network_measurement.network.kind", read_only=True)
    device_name = serializers.CharField(source="network_measurement.device.name", read_only=True, allow_null=True)
    device_code = serializers.CharField(source="network_measurement.device.device_code", read_only=True, allow_null=True)
    location_name = serializers.CharField(source="network_measurement.location.display_name", read_only=True)
    latency_ms = serializers.DecimalField(source="network_measurement.latency_ms", max_digits=9, decimal_places=2, read_only=True, allow_null=True)
    packet_loss_percent = serializers.DecimalField(source="network_measurement.packet_loss_percent", max_digits=5, decimal_places=2, read_only=True, allow_null=True)
    download_mbps = serializers.DecimalField(source="network_measurement.download_mbps", max_digits=12, decimal_places=3, read_only=True, allow_null=True)
    upload_mbps = serializers.DecimalField(source="network_measurement.upload_mbps", max_digits=12, decimal_places=3, read_only=True, allow_null=True)
    signal_strength_dbm = serializers.IntegerField(source="network_measurement.signal_strength_dbm", read_only=True, allow_null=True)
    connection_state = serializers.CharField(source="network_measurement.connection_state", read_only=True)

    class Meta:
        model = IssueNetworkContext
        fields = (
            "id", "issue", "measurement_id", "created_by", "created_at", "evaluator_version",
            "overall_quality", "primary_factor", "measured_at", "network_name", "network_kind",
            "device_name", "device_code", "location_name", "latency_ms", "packet_loss_percent",
            "download_mbps", "upload_mbps", "signal_strength_dbm", "connection_state",
        )
        read_only_fields = fields
