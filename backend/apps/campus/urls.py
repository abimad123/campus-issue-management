from rest_framework.routers import DefaultRouter

from .views import BuildingViewSet, CampusViewSet, DepartmentViewSet, LocationViewSet, TeamViewSet

router = DefaultRouter()
router.register("campuses", CampusViewSet)
router.register("buildings", BuildingViewSet, basename="building")
router.register("locations", LocationViewSet, basename="location")
router.register("departments", DepartmentViewSet)
router.register("teams", TeamViewSet)
urlpatterns = router.urls
