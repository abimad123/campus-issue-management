from django.contrib import admin

from .models import Network, NetworkDevice, NetworkMeasurement


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "campus", "building", "is_active")
    list_filter = ("kind", "campus", "is_active")
    search_fields = ("code", "name", "campus__name", "building__name")
    list_select_related = ("campus", "building")


@admin.register(NetworkDevice)
class NetworkDeviceAdmin(admin.ModelAdmin):
    list_display = ("device_code", "name", "kind", "network", "location", "state")
    list_filter = ("kind", "state", "network__campus")
    search_fields = ("device_code", "name", "network__name", "serial_number")
    list_select_related = ("network", "location", "asset")


@admin.register(NetworkMeasurement)
class NetworkMeasurementAdmin(admin.ModelAdmin):
    list_display = ("id", "network", "location", "measured_at", "connection_state", "recorded_by")
    list_filter = ("network", "connection_state", "measured_at")
    list_select_related = ("network", "location", "recorded_by")
    readonly_fields = tuple(field.name for field in NetworkMeasurement._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
