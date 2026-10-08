from pathlib import Path

from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from apps.campus.models import Team
from apps.issues.access import visible_issues_for
from apps.issues.models import Issue
from apps.users.models import User
from apps.users.roles import ISSUE_MANAGEMENT_ROLES, UserRole

from .models import WorkOrder, WorkOrderEvidence, WorkOrderMaterial, WorkOrderNote
from .serializers import (
    AssignWorkOrderSerializer, CreateWorkOrderSerializer, MaterialSerializer,
    NoteSerializer, ReasonSerializer, ResolutionSerializer, WorkOrderDetailSerializer,
    WorkOrderEvidenceSerializer, WorkOrderEvidenceUploadSerializer, WorkOrderListSerializer,
    WorkOrderMaterialSerializer, WorkOrderNoteSerializer,
)
from .services import (
    accept_work_order, add_material, add_note, assign_work_order, cancel_work_order,
    close_work_order, complete_work_order, create_work_order, get_visible_work_order,
    reject_work_order, require_technician, start_work_order, verify_work_order,
    visible_work_orders_for,
)


class IssueWorkOrderCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, issue_id):
        if not visible_issues_for(request.user).filter(pk=issue_id).exists():
            from rest_framework.exceptions import NotFound
            raise NotFound()
        queryset = visible_work_orders_for(request.user).filter(issue_id=issue_id).select_related("team", "assigned_to", "issue")
        page = self.paginate_queryset(queryset)
        serializer = WorkOrderListSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    def paginate_queryset(self, queryset):
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        paginator.page_size = 20
        self._paginator = paginator
        return paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        return self._paginator.get_paginated_response(data)

    def post(self, request, issue_id):
        issue = get_object_or_404(visible_issues_for(request.user).select_related("assigned_team"), pk=issue_id)
        serializer = CreateWorkOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = get_object_or_404(Team, pk=serializer.validated_data["team"])
        work_order = create_work_order(
            issue=issue, actor=request.user, team=team,
            title=serializer.validated_data.get("title") or None,
            instructions=serializer.validated_data.get("instructions", ""),
        )
        return Response(WorkOrderDetailSerializer(work_order, context={"request": request}).data, status=status.HTTP_201_CREATED)


class WorkOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "team", "assigned_to", "issue"]

    def get_queryset(self):
        return visible_work_orders_for(self.request.user).select_related(
            "issue__category", "issue__location__building", "issue__sla_policy", "team", "assigned_to", "created_by", "completed_by", "verified_by",
        ).prefetch_related("assignments__team", "assignments__technician", "assignments__assigned_by", "events__actor", "notes__author", "materials__recorded_by", "evidence__uploaded_by")

    def get_serializer_class(self):
        return WorkOrderListSerializer if self.action == "list" else WorkOrderDetailSerializer

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        queryset = visible_work_orders_for(request.user)
        return Response({
            "open": queryset.filter(status__in=[WorkOrder.Status.ASSIGNED, WorkOrder.Status.ACCEPTED, WorkOrder.Status.REWORK]).count(),
            "in_progress": queryset.filter(status=WorkOrder.Status.IN_PROGRESS).count(),
            "awaiting_verification": queryset.filter(status=WorkOrder.Status.COMPLETED).count(),
            "verified": queryset.filter(status__in=[WorkOrder.Status.VERIFIED, WorkOrder.Status.CLOSED]).count(),
        })

    def _locked(self, pk):
        return get_visible_work_order(self.request.user, pk, lock=True)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        with transaction.atomic():
            work_order = self._locked(pk)
            serializer = AssignWorkOrderSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            team = get_object_or_404(Team, pk=data.get("team", work_order.team_id))
            technician = None
            if "technician" in data and data["technician"] is not None:
                from apps.users.models import User
                technician = get_object_or_404(User, pk=data["technician"])
            elif "technician" not in data:
                technician = work_order.assigned_to
            result = assign_work_order(work_order=work_order, actor=request.user, team=team, technician=technician, reason=data["reason"])
        return Response(WorkOrderDetailSerializer(result, context={"request": request}).data)

    def _action(self, request, pk, service, **kwargs):
        with transaction.atomic():
            work_order = self._locked(pk)
            result = service(work_order=work_order, actor=request.user, **kwargs)
        if isinstance(result, WorkOrderNote):
            return Response(WorkOrderNoteSerializer(result).data)
        if isinstance(result, WorkOrderMaterial):
            return Response(WorkOrderMaterialSerializer(result).data)
        return Response(WorkOrderDetailSerializer(result, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return self._action(request, pk, accept_work_order)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return self._action(request, pk, start_work_order)

    @action(detail=True, methods=["post"], url_path="notes")
    def notes(self, request, pk=None):
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._action(request, pk, add_note, body=serializer.validated_data["body"])

    @action(detail=True, methods=["post"], url_path="materials")
    def materials(self, request, pk=None):
        serializer = MaterialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._action(request, pk, add_material, **serializer.validated_data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser], url_path="evidence")
    def evidence_upload(self, request, pk=None):
        with transaction.atomic():
            work_order = self._locked(pk)
            require_technician(request.user, work_order)
            if work_order.status not in {WorkOrder.Status.ACCEPTED, WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.REWORK}:
                raise ValidationError({"status": "Evidence can be added after accepting work and before completion."})
            serializer = WorkOrderEvidenceUploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            evidence = serializer.save(work_order=work_order, uploaded_by=request.user)
            from .services import _event
            _event(work_order, request.user, "EVIDENCE_ADDED", note="Private work evidence uploaded")
        return Response(WorkOrderEvidenceSerializer(evidence, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        serializer = ResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._action(request, pk, complete_work_order, resolution_summary=serializer.validated_data["resolution_summary"])

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        return self._action(request, pk, verify_work_order)

    @action(detail=True, methods=["post"])
    def rework(self, request, pk=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._action(request, pk, reject_work_order, reason=serializer.validated_data["reason"])

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._action(request, pk, cancel_work_order, reason=serializer.validated_data["reason"])

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._action(request, pk, close_work_order)


class WorkOrderEvidenceFileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        evidence = get_object_or_404(
            WorkOrderEvidence.objects.select_related("work_order"),
            pk=pk,
            work_order__in=visible_work_orders_for(request.user),
        )
        response = FileResponse(
            evidence.file.open("rb"), content_type=evidence.content_type,
            filename=Path(evidence.file.name).name,
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class WorkOrderTechnicianOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ISSUE_MANAGEMENT_ROLES | {UserRole.SUPERVISOR}:
            raise PermissionDenied("Only operational managers may select technicians.")
        try:
            team_id = int(request.query_params.get("team", ""))
        except ValueError:
            raise ValidationError({"team": "Choose a valid team."}) from None
        team = get_object_or_404(Team, pk=team_id, is_active=True)
        if request.user.role == UserRole.SUPERVISOR and not request.user.teams.filter(pk=team.pk, is_active=True).exists():
            raise PermissionDenied("Supervisors may select technicians only in their own teams.")
        users = User.objects.filter(role=UserRole.TECHNICIAN, is_active=True, teams=team).order_by("full_name", "pk")
        return Response([{"id": user.pk, "full_name": user.full_name, "email": user.email} for user in users])
