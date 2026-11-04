from django.db import transaction
from django.urls import reverse
from rest_framework import serializers

from apps.assets.models import Asset
from apps.campus.models import Location
from apps.users.roles import UserRole

from .models import Issue, IssueAttachment, IssueCategory, IssueEvent, IssuePriorityEvent
from .services import transition_issue


class IssueCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueCategory
        fields = ("id", "name", "description", "icon_identifier", "is_active", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")


class IssueAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = IssueAttachment
        fields = ("id", "file_url", "content_type", "uploaded_by", "uploaded_by_name", "created_at")

    def get_file_url(self, obj):
        path = reverse("issue-attachment-file", kwargs={"pk": obj.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class IssueEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, allow_null=True)

    class Meta:
        model = IssueEvent
        fields = ("id", "from_status", "to_status", "note", "actor_name", "created_at")


class IssueListSerializer(serializers.ModelSerializer):
    category = IssueCategorySerializer(read_only=True)
    location_name = serializers.CharField(source="location.display_name", read_only=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True, allow_null=True)
    reporter_name = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    assigned_team = serializers.SerializerMethodField()
    assigned_team_name = serializers.SerializerMethodField()
    sla_state = serializers.SerializerMethodField()
    response_sla_state = serializers.SerializerMethodField()
    resolution_sla_state = serializers.SerializerMethodField()

    class Meta:
        model = Issue
        fields = ("id", "ticket_number", "title", "category", "location", "location_name", "asset", "asset_name", "reporter", "reporter_name", "assigned_to", "assigned_to_name", "assigned_team", "assigned_team_name", "priority", "status", "created_at", "updated_at", "resolved_at", "closed_at", "sla_state", "response_sla_state", "resolution_sla_state")

    def get_reporter_name(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and (user.id == obj.reporter_id or user.role == UserRole.ADMIN):
            return obj.reporter.full_name
        return None

    def _is_operational(self):
        request = self.context.get("request")
        return request and request.user.role in {UserRole.TECHNICAL_STAFF, UserRole.ADMIN}

    def get_assigned_to(self, obj): return obj.assigned_to_id if self._is_operational() else None
    def get_assigned_team(self, obj): return obj.assigned_team_id if self._is_operational() else None
    def get_assigned_to_name(self, obj): return obj.assigned_to.full_name if self._is_operational() and obj.assigned_to_id else None
    def get_assigned_team_name(self, obj): return obj.assigned_team.name if self._is_operational() and obj.assigned_team_id else None

    def get_sla_state(self, obj):
        if not self._is_operational():
            return None
        if obj.status in {Issue.Status.RESOLVED, Issue.Status.CLOSED}:
            return "COMPLETED"
        states = {self.get_response_sla_state(obj), self.get_resolution_sla_state(obj)}
        if "BREACHED" in states:
            return "BREACHED"
        if "AT_RISK" in states:
            return "AT_RISK"
        return "ON_TRACK" if obj.sla_policy_id else "NOT_CONFIGURED"

    def _state_for_deadline(self, obj, deadline, breached_at, completed):
        from django.utils import timezone
        if not self._is_operational():
            return None
        if breached_at:
            return "BREACHED"
        if completed:
            return "COMPLETED"
        if not obj.sla_policy_id or not deadline:
            return "NOT_CONFIGURED"
        remaining = (deadline - timezone.now()).total_seconds()
        if remaining <= 0:
            return "BREACHED"
        if remaining <= obj.sla_policy.warning_before_seconds:
            return "AT_RISK"
        return "ON_TRACK"

    def get_response_sla_state(self, obj):
        return self._state_for_deadline(obj, obj.response_due_at, obj.response_breached_at, obj.status in {Issue.Status.IN_PROGRESS, Issue.Status.RESOLVED, Issue.Status.CLOSED})

    def get_resolution_sla_state(self, obj):
        return self._state_for_deadline(obj, obj.resolution_due_at, obj.resolution_breached_at, obj.status in {Issue.Status.RESOLVED, Issue.Status.CLOSED})


class IssueDetailSerializer(IssueListSerializer):
    description = serializers.CharField(read_only=True)
    reporter_email = serializers.SerializerMethodField()
    attachments = IssueAttachmentSerializer(many=True, read_only=True)
    events = IssueEventSerializer(many=True, read_only=True)
    response_due_at = serializers.SerializerMethodField()
    resolution_due_at = serializers.SerializerMethodField()
    sla_policy_name = serializers.SerializerMethodField()
    response_breached_at = serializers.SerializerMethodField()
    resolution_breached_at = serializers.SerializerMethodField()
    current_escalation_level = serializers.SerializerMethodField()
    assignment_history = serializers.SerializerMethodField()

    class Meta(IssueListSerializer.Meta):
        fields = IssueListSerializer.Meta.fields + ("description", "reporter_email", "attachments", "events", "response_due_at", "resolution_due_at", "sla_policy_name", "response_breached_at", "resolution_breached_at", "current_escalation_level", "assignment_history", "priority_requested_by", "priority_requested_by_name", "priority_requested_at", "priority_request_reason", "priority_history")

    priority_requested_by_name = serializers.CharField(source="priority_requested_by.full_name", read_only=True, allow_null=True)
    priority_history = serializers.SerializerMethodField()

    def _is_operational(self):
        return super()._is_operational()

    def get_response_due_at(self, obj): return obj.response_due_at if self._is_operational() else None
    def get_resolution_due_at(self, obj): return obj.resolution_due_at if self._is_operational() else None
    def get_sla_policy_name(self, obj): return obj.sla_policy.name if self._is_operational() and obj.sla_policy_id else None
    def get_response_breached_at(self, obj): return obj.response_breached_at if self._is_operational() else None
    def get_resolution_breached_at(self, obj): return obj.resolution_breached_at if self._is_operational() else None
    def get_current_escalation_level(self, obj): return obj.current_escalation_level if self._is_operational() else None

    def get_assignment_history(self, obj):
        if not self._is_operational(): return []
        return [{"team": a.team.name if a.team_id else None, "user": a.user.full_name if a.user_id else None, "reason": a.reason, "automatic": a.is_automatic, "rule": a.routing_rule.name if a.routing_rule_id else None, "created_at": a.created_at} for a in obj.assignments.select_related("team", "user", "routing_rule")]

    def get_reporter_email(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and (user.id == obj.reporter_id or user.role == UserRole.ADMIN):
            return obj.reporter.email
        return None

    def get_priority_history(self, obj):
        request = self.context.get("request")
        if not request or request.user.role != UserRole.ADMIN:
            return []
        return [{"old_priority": item.old_priority, "new_priority": item.new_priority, "reason": item.reason, "actor": item.actor.full_name if item.actor_id else None, "created_at": item.created_at} for item in obj.priority_events.select_related("actor")]


class IssueCreateSerializer(serializers.ModelSerializer):
    photo = serializers.ImageField(write_only=True, required=False)
    request_priority = serializers.BooleanField(write_only=True, required=False, default=False)
    priority_reason = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=500)

    class Meta:
        model = Issue
        fields = ("id", "ticket_number", "title", "description", "category", "location", "asset", "priority", "status", "created_at", "photo", "request_priority", "priority_reason")
        read_only_fields = ("id", "ticket_number", "status", "created_at")

    def validate_category(self, category):
        if not category.is_active:
            raise serializers.ValidationError("Choose an active category.")
        return category

    def validate_location(self, location):
        if not location.is_active:
            raise serializers.ValidationError("Choose an active location.")
        return location

    def validate_asset(self, asset):
        if asset and not asset.is_active:
            raise serializers.ValidationError("Choose an active asset.")
        return asset

    def validate_photo(self, photo):
        from .validators import validate_issue_image
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            validate_issue_image(photo)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return photo

    def validate(self, attrs):
        from rest_framework.exceptions import ValidationError
        user = self.context["request"].user
        request_priority = attrs.get("request_priority", False)
        if "priority" in self.initial_data and user.role != UserRole.ADMIN:
            raise ValidationError({"priority": "Only administrators may set priority directly; staff can request priority handling."})
        if request_priority and "priority" in self.initial_data:
            raise ValidationError({"priority": "Remove the direct priority value when requesting priority handling."})
        if request_priority and user.role != UserRole.STAFF:
            raise ValidationError({"request_priority": "Only staff accounts may request priority handling."})
        if request_priority and len((attrs.get("priority_reason") or "").strip()) < 5:
            raise ValidationError({"priority_reason": "Provide at least 5 characters explaining the priority request."})
        if not request_priority and attrs.get("priority_reason"):
            raise ValidationError({"priority_reason": "A reason is accepted only with a priority request."})
        asset = attrs.get("asset")
        location = attrs.get("location")
        if asset and location and asset.location_id != location.id:
            raise serializers.ValidationError({"asset": "The selected asset is not recorded at this location."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        from django.utils import timezone
        from apps.audit.services import record_audit
        from .models import IssuePriorityEvent
        photo = validated_data.pop("photo", None)
        request_priority = validated_data.pop("request_priority", False)
        priority_reason = validated_data.pop("priority_reason", "").strip()
        validated_data["routing_priority"] = validated_data.get("priority", Issue.Priority.MEDIUM)
        if request_priority:
            validated_data["priority"] = Issue.Priority.HIGH
            validated_data["priority_requested_by"] = self.context["request"].user
            validated_data["priority_requested_at"] = timezone.now()
            validated_data["priority_request_reason"] = priority_reason
        issue = Issue.objects.create(reporter=self.context["request"].user, **validated_data)
        if request_priority:
            IssuePriorityEvent.objects.create(issue=issue, actor=issue.reporter, old_priority=Issue.Priority.MEDIUM, new_priority=Issue.Priority.HIGH, reason=priority_reason)
            record_audit("issue.priority_requested", actor=issue.reporter, entity=issue, context={"priority": Issue.Priority.HIGH, "reason": priority_reason})
        IssueEvent.objects.create(issue=issue, actor=issue.reporter, to_status=Issue.Status.OPEN, note="Issue submitted")
        if photo:
            IssueAttachment.objects.create(issue=issue, file=photo, uploaded_by=issue.reporter)
        from apps.routing.services import route_issue
        from apps.sla.services import start_sla
        route_issue(issue)
        start_sla(issue)
        return issue


class IssueStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Issue.Status.choices)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def save(self, **kwargs):
        return transition_issue(
            self.context["issue"],
            new_status=self.validated_data["status"],
            actor=self.context["request"].user,
            note=self.validated_data.get("note", ""),
        )


class IssuePriorityUpdateSerializer(serializers.Serializer):
    priority = serializers.ChoiceField(choices=Issue.Priority.choices)
    reason = serializers.CharField(min_length=5, max_length=500)
