import django_filters

from .models import Network, NetworkDevice, NetworkMeasurement


class NetworkFilter(django_filters.FilterSet):
    class Meta:
        model = Network
        fields = ("campus", "building", "kind", "is_active")


class NetworkDeviceFilter(django_filters.FilterSet):
    class Meta:
        model = NetworkDevice
        fields = ("network", "kind", "location", "state")


class NetworkMeasurementFilter(django_filters.FilterSet):
    measured_after = django_filters.IsoDateTimeFilter(field_name="measured_at", lookup_expr="gte")
    measured_before = django_filters.IsoDateTimeFilter(field_name="measured_at", lookup_expr="lte")

    class Meta:
        model = NetworkMeasurement
        fields = ("network", "device", "location", "connection_state", "recorded_by")
