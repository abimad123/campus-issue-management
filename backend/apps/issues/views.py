from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.db.models import Case, IntegerField, Q, Value, When
from rest_framework.response import Response

from .access import visible_issues_for
from .filters import IssueFilter
from .models import Issue, IssueCategory
from .permissions import IssuePermission
from .serializers import (
    IssueCategorySerializer,
    IssueCreateSerializer,
    IssueDetailSerializer,
    IssueListSerializer,
    IssuePriorityUpdateSerializer,
    IssueStatusSerializer,
)
from apps.network.models import IssueNetworkContext
from apps.network.permissions import CanReadNetworkOperations
from apps.network.serializers import IssueNetworkContextCreateSerializer, IssueNetworkContextSerializer
from apps.network.services import attach_network_context


class IssueCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = IssueCategorySerializer

    def get_queryset(self):
        return IssueCategory.objects.filter(is_active=True)

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated()]
        from apps.users.permissions import IsCampusAdministrator
        return [IsCampusAdministrator()]


class IssueViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IssuePermission]
    filterset_class = IssueFilter
    ordering_fields = ["created_at", "priority", "status"]
    ordering = ["priority_rank", "-created_at"]

    def get_queryset(self):
        queryset = visible_issues_for(self.request.user).annotate(priority_rank=Case(
            When(priority=Issue.Priority.CRITICAL, then=Value(0)),
            When(priority=Issue.Priority.HIGH, then=Value(1)),
            When(priority=Issue.Priority.MEDIUM, then=Value(2)),
            default=Value(3), output_field=IntegerField(),
        )).select_related(
            "category", "location__building__campus", "asset", "reporter", "assigned_to", "assigned_team", "sla_policy"
        ).prefetch_related("attachments__uploaded_by", "events__actor", "assignments__team", "assignments__user", "assignments__routing_rule")
        return queryset

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = visible_issues_for(request.user)
        active = qs.exclude(status__in=[Issue.Status.RESOLVED, Issue.Status.CLOSED])
        risk = active.filter(sla_events__event_type__in=["RESPONSE_WARNING", "RESOLUTION_WARNING"]).distinct()
        return Response({
            "open": active.count(),
            "assigned": active.filter(assigned_to__isnull=False).count(),
            "at_risk": risk.count(),
            "breached": qs.filter(Q(response_breached_at__isnull=False) | Q(resolution_breached_at__isnull=False)).count(),
            "unassigned": active.filter(assigned_to__isnull=True).count(),
            "priority_requests": qs.filter(priority_requested_at__isnull=False).count(),
            "automatically_assigned": qs.filter(assignments__is_automatic=True).distinct().count(),
        })

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
        serializer = IssueStatusSerializer(data=request.data, context={"issue": issue, "request": request})
        serializer.is_valid(raise_exception=True)
        issue = serializer.save()
        return Response(IssueDetailSerializer(issue, context=self.get_serializer_context()).data)

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[IssuePermission, CanReadNetworkOperations],
        url_path="network-context",
    )
    def network_context(self, request, pk=None):
        issue = self.get_object()
        if request.method == "GET":
            contexts = IssueNetworkContext.objects.filter(issue=issue).select_related(
                "network_measurement__network",
                "network_measurement__device",
                "network_measurement__location__building",
                "created_by",
            )
            page = self.paginate_queryset(contexts)
            result = IssueNetworkContextSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(result.data)

        context_input = IssueNetworkContextCreateSerializer(data=request.data)
        context_input.is_valid(raise_exception=True)
        context = attach_network_context(
            issue=issue,
            measurement=context_input.validated_data["network_measurement"],
            actor=request.user,
        )
        result = IssueNetworkContextSerializer(context, context=self.get_serializer_context())
        return Response(result.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IssuePermission], url_path="priority")
    def priority(self, request, pk=None):
        from django.db import transaction
        from rest_framework.exceptions import PermissionDenied
        from apps.users.roles import UserRole
        from apps.audit.services import record_audit
        from .models import IssuePriorityEvent

        if request.user.role != UserRole.ADMIN:
            raise PermissionDenied("Only administrators may change issue priority.")
        serializer = IssuePriorityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            issue = Issue.objects.select_for_update().get(pk=self.get_object().pk)
            old_priority = issue.priority
            new_priority = serializer.validated_data["priority"]
            reason = serializer.validated_data["reason"].strip()
            if old_priority != new_priority:
                issue.priority = new_priority
                issue.save(update_fields=["priority", "updated_at"])
                IssuePriorityEvent.objects.create(issue=issue, actor=request.user, old_priority=old_priority, new_priority=new_priority, reason=reason)
                record_audit("issue.priority_changed", actor=request.user, entity=issue, context={"old_priority": old_priority, "new_priority": new_priority, "reason": reason})
        return Response(IssueDetailSerializer(issue, context=self.get_serializer_context()).data)
