from rest_framework.routers import DefaultRouter

from .views import NetworkDeviceViewSet, NetworkMeasurementViewSet, NetworkViewSet

router = DefaultRouter()
router.register("networks", NetworkViewSet, basename="network")
router.register("network-devices", NetworkDeviceViewSet, basename="network-device")
router.register("network-measurements", NetworkMeasurementViewSet, basename="network-measurement")
urlpatterns = router.urls
