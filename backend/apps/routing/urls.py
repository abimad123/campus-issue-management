from rest_framework.routers import DefaultRouter
from django.urls import include, path
from .views import IssueAssignmentViewSet, RoutingRuleViewSet

router = DefaultRouter()
router.register("admin/routing-rules", RoutingRuleViewSet, basename="routing-rule")
urlpatterns = [path("issues/<int:pk>/assign/", IssueAssignmentViewSet.as_view({"post": "assign"}), name="issue-assign"), path("", include(router.urls))]
