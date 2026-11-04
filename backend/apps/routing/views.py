from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from apps.audit.services import record_audit
from apps.campus.models import Team
from apps.issues.models import Issue, IssueEvent
from apps.notifications.models import Notification
from apps.issues.access import visible_issues_for
from apps.users.roles import UserRole, ADMIN_ROLES
from .models import Assignment, RoutingRule
from .serializers import ManualAssignmentSerializer, RoutingRuleSerializer


class RoutingRuleViewSet(viewsets.ModelViewSet):
    queryset = RoutingRule.objects.select_related("category", "location", "target_team", "target_user")
    serializer_class = RoutingRuleSerializer

    def get_permissions(self):
        from apps.users.permissions import IsCampusAdministrator
        return [IsCampusAdministrator()]

    def perform_create(self, serializer):
        rule = serializer.save(created_by=self.request.user)
        record_audit("routing_rule.created", actor=self.request.user, entity=rule)

    def perform_update(self, serializer):
        rule = serializer.save()
        record_audit("routing_rule.updated", actor=self.request.user, entity=rule)


class IssueAssignmentViewSet(viewsets.GenericViewSet):
    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="assign")
    def assign(self, request, pk=None):
        visible_issue_id = visible_issues_for(request.user).filter(pk=pk).values_list("pk", flat=True).first()
        if visible_issue_id is None:
            raise NotFound()
        # Keep the visibility query separate from the row lock: supervisor visibility
        # uses DISTINCT across team membership, which PostgreSQL cannot lock directly.
        issue = Issue.objects.select_for_update().get(pk=visible_issue_id)
        if request.user.role != UserRole.ADMIN:
            raise PermissionDenied("You are not allowed to reassign issues.")
        serializer = ManualAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team = Team.objects.filter(pk=serializer.validated_data["team"], is_active=True).first()
        if not team:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"team": "Choose an active team."})
        user_id = serializer.validated_data.get("user")
        assignee = team.members.filter(pk=user_id, is_active=True, role=UserRole.TECHNICAL_STAFF).first()
        if not assignee:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"user": "Choose active technical staff belonging to the selected team."})
        with transaction.atomic():
            old_team = issue.assigned_team_id
            old_status = issue.status
            issue.assigned_team = team
            issue.assigned_to = assignee
            if issue.status == Issue.Status.OPEN:
                issue.status = Issue.Status.ASSIGNED
            issue.save(update_fields=["assigned_team", "assigned_to", "status", "updated_at"])
            assignment = Assignment.objects.create(issue=issue, team=team, user=assignee, assigned_by=request.user, reason=serializer.validated_data["reason"])
            if old_status != issue.status:
                IssueEvent.objects.create(issue=issue, actor=request.user, from_status=old_status, to_status=issue.status, note=f"Assigned to {team.name}: {assignment.reason}")
            Notification.objects.get_or_create(recipient=assignee, issue=issue, notification_type="ISSUE_ASSIGNED", defaults={"title": "Issue assigned to you", "message": f"{issue.ticket_number}: {issue.title}"})
            record_audit("issue.reassigned" if old_team else "issue.assigned", actor=request.user, entity=assignment, context={"issue_id": issue.pk, "team_id": team.pk, "technician_id": assignee.pk, "previous_team_id": old_team})
        return Response({"id": assignment.pk, "team": team.name, "user": assignee.full_name if assignee else None, "reason": assignment.reason}, status=status.HTTP_201_CREATED)
