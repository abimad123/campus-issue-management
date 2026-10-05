from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.roles import ISSUE_MANAGEMENT_ROLES, UserRole

from .access import visible_issues_for
from .filters import IssueFilter
from .models import Issue, IssueCategory
from .permissions import IssuePermission
from .serializers import (
    IssueCategorySerializer,
    IssueCreateSerializer,
    IssueDetailSerializer,
    IssueListSerializer,
    IssueStatusSerializer,
)


class IssueCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = IssueCategorySerializer

    def get_queryset(self):
        queryset = IssueCategory.objects.all()
        if self.request.user.role not in ISSUE_MANAGEMENT_ROLES:
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        from apps.users.permissions import IsCampusAdministrator
        return [IsCampusAdministrator()]


class IssueViewSet(viewsets.ModelViewSet):
    permission_classes = [IssuePermission]
    filterset_class = IssueFilter
    ordering_fields = ["created_at", "priority", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = visible_issues_for(self.request.user).select_related(
            "category", "location__building__campus", "asset", "reporter", "assigned_to", "assigned_team"
        ).prefetch_related("attachments__uploaded_by", "events__actor")
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return IssueCreateSerializer
        if self.action == "status":
            return IssueStatusSerializer
        if self.action == "retrieve":
            return IssueDetailSerializer
        return IssueListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        issue = serializer.save()
        output = IssueDetailSerializer(issue, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED, headers=self.get_success_headers(output.data))

    @action(detail=True, methods=["post"], permission_classes=[IssuePermission], url_path="status")
    def status(self, request, pk=None):
        issue = self.get_object()
        if request.user.role not in ISSUE_MANAGEMENT_ROLES and not (
            request.user.role == UserRole.TECHNICIAN and issue.assigned_to_id == request.user.id
        ) and not (
            request.user.role == UserRole.SUPERVISOR and issue.assigned_team_id in request.user.teams.values_list("id", flat=True)
        ):
            raise PermissionDenied("You cannot change the status of this issue.")
        serializer = IssueStatusSerializer(data=request.data, context={"issue": issue, "request": request})
        serializer.is_valid(raise_exception=True)
        issue = serializer.save()
        return Response(IssueDetailSerializer(issue, context=self.get_serializer_context()).data)
