from django.urls import reverse
from decimal import Decimal
from rest_framework import serializers

from .models import WorkOrder, WorkOrderAssignment, WorkOrderEvidence, WorkOrderEvent, WorkOrderMaterial, WorkOrderNote


class WorkOrderEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, allow_null=True)

    class Meta:
        model = WorkOrderEvent
        fields = ("id", "event_type", "from_status", "to_status", "note", "actor_name", "created_at")


class WorkOrderAssignmentSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True)
    technician_name = serializers.CharField(source="technician.full_name", read_only=True, allow_null=True)
    assigned_by_name = serializers.CharField(source="assigned_by.full_name", read_only=True, allow_null=True)

    class Meta:
        model = WorkOrderAssignment
        fields = ("id", "team", "team_name", "technician", "technician_name", "assigned_by_name", "reason", "created_at")


class WorkOrderNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)

    class Meta:
        model = WorkOrderNote
        fields = ("id", "author", "author_name", "body", "created_at")
        read_only_fields = fields


class WorkOrderMaterialSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True)

    class Meta:
        model = WorkOrderMaterial
        fields = ("id", "name", "quantity", "note", "recorded_by_name", "created_at")
        read_only_fields = fields


class WorkOrderEvidenceSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrderEvidence
        fields = ("id", "file_url", "content_type", "caption", "uploaded_by", "uploaded_by_name", "created_at")

    def get_file_url(self, obj):
        path = reverse("work-order-evidence-file", kwargs={"pk": obj.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class WorkOrderListSerializer(serializers.ModelSerializer):
    issue_ticket_number = serializers.CharField(source="issue.ticket_number", read_only=True)
    issue_title = serializers.CharField(source="issue.title", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True, allow_null=True)

    class Meta:
        model = WorkOrder
        fields = ("id", "number", "issue", "issue_ticket_number", "issue_title", "team", "team_name", "assigned_to", "assigned_to_name", "title", "priority", "status", "created_at", "accepted_at", "started_at", "completed_at", "verified_at", "closed_at")


class WorkOrderDetailSerializer(WorkOrderListSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, allow_null=True)
    completed_by_name = serializers.CharField(source="completed_by.full_name", read_only=True, allow_null=True)
    verified_by_name = serializers.CharField(source="verified_by.full_name", read_only=True, allow_null=True)
    issue_sla_deadline = serializers.DateTimeField(source="issue.resolution_due_at", read_only=True, allow_null=True)
    assignments = WorkOrderAssignmentSerializer(many=True, read_only=True)
    events = WorkOrderEventSerializer(many=True, read_only=True)
    notes = WorkOrderNoteSerializer(many=True, read_only=True)
    materials = WorkOrderMaterialSerializer(many=True, read_only=True)
    evidence = WorkOrderEvidenceSerializer(many=True, read_only=True)

    class Meta(WorkOrderListSerializer.Meta):
        fields = WorkOrderListSerializer.Meta.fields + ("instructions", "created_by", "created_by_name", "completed_by", "completed_by_name", "verified_by", "verified_by_name", "resolution_summary", "cancellation_reason", "rework_reason", "issue_sla_deadline", "updated_at", "assignments", "events", "notes", "materials", "evidence")


class CreateWorkOrderSerializer(serializers.Serializer):
    team = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=160, required=False, allow_blank=True)
    instructions = serializers.CharField(max_length=5000, required=False, allow_blank=True)


class AssignWorkOrderSerializer(serializers.Serializer):
    team = serializers.IntegerField(min_value=1, required=False)
    technician = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    reason = serializers.CharField(min_length=3, max_length=500)


class NoteSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=2, max_length=5000, trim_whitespace=True)


class MaterialSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160, trim_whitespace=True)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ResolutionSerializer(serializers.Serializer):
    resolution_summary = serializers.CharField(min_length=20, max_length=5000, trim_whitespace=True)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)


class VerifySerializer(serializers.Serializer):
    verified = serializers.BooleanField(default=True)


class WorkOrderEvidenceUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkOrderEvidence
        fields = ("file", "caption")
