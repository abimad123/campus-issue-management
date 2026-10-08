from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IssueWorkOrderCollectionView, WorkOrderEvidenceFileView, WorkOrderTechnicianOptionsView, WorkOrderViewSet

router = DefaultRouter()
router.register("work-orders", WorkOrderViewSet, basename="work-order")

urlpatterns = [
    path("issues/<int:issue_id>/work-orders/", IssueWorkOrderCollectionView.as_view(), name="issue-work-orders"),
    path("work-order-technicians/", WorkOrderTechnicianOptionsView.as_view(), name="work-order-technicians"),
    path("work-order-evidence/<int:pk>/file/", WorkOrderEvidenceFileView.as_view(), name="work-order-evidence-file"),
    path("", include(router.urls)),
]
