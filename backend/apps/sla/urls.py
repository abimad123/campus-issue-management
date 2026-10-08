from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import SlaPolicyViewSet

router = DefaultRouter()
router.register("admin/sla-policies", SlaPolicyViewSet, basename="sla-policy")
urlpatterns = [path("", include(router.urls))]
