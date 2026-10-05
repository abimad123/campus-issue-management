from django.urls import path
from rest_framework.routers import DefaultRouter

from .attachment_views import IssueAttachmentFileView
from .views import IssueCategoryViewSet, IssueViewSet

router = DefaultRouter()
router.register("issue-categories", IssueCategoryViewSet, basename="issue-category")
router.register("issues", IssueViewSet, basename="issue")
urlpatterns = router.urls + [
    path("issue-attachments/<int:pk>/file/", IssueAttachmentFileView.as_view(), name="issue-attachment-file"),
]
