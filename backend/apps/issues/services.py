from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.users.roles import ISSUE_MANAGEMENT_ROLES, UserRole

from .models import Issue, IssueEvent

ALLOWED_TRANSITIONS = {
    Issue.Status.OPEN: {Issue.Status.IN_REVIEW},
    Issue.Status.IN_REVIEW: {Issue.Status.ASSIGNED},
    Issue.Status.ASSIGNED: {Issue.Status.IN_PROGRESS},
    Issue.Status.IN_PROGRESS: {Issue.Status.RESOLVED},
    Issue.Status.RESOLVED: {Issue.Status.CLOSED, Issue.Status.REOPENED},
    Issue.Status.CLOSED: {Issue.Status.REOPENED},
    Issue.Status.REOPENED: {Issue.Status.IN_REVIEW},
}


def can_change_issue_status(user, issue):
    if user.role in ISSUE_MANAGEMENT_ROLES:
        return True
    if user.role == UserRole.TECHNICIAN:
        return issue.assigned_to_id == user.id
    if user.role == UserRole.SUPERVISOR:
        return issue.assigned_team_id in user.teams.values_list("id", flat=True)
    return False


@transaction.atomic
def transition_issue(issue, *, new_status, actor, note=""):
    # Refresh the caller's instance under a row lock so concurrent transitions
    # validate against the latest committed status and assignment.
    locked_issue = Issue.objects.select_for_update().get(pk=issue.pk)
    issue.__dict__.update(locked_issue.__dict__)
    if not can_change_issue_status(actor, issue):
        raise PermissionDenied("You are not allowed to update this issue status.")
    if actor.role == UserRole.TECHNICIAN and new_status in {
        Issue.Status.RESOLVED,
        Issue.Status.CLOSED,
        Issue.Status.REOPENED,
    }:
        raise PermissionDenied("Technicians must complete work through work-order verification before resolving an issue.")
    if new_status not in ALLOWED_TRANSITIONS.get(issue.status, set()):
        raise ValidationError({"status": f"Cannot change an issue from {issue.status} to {new_status}."})

    old_status = issue.status
    now = timezone.now()
    issue.status = new_status
    if new_status == Issue.Status.IN_PROGRESS and issue.response_at is None:
        issue.response_at = now
    if new_status == Issue.Status.RESOLVED:
        issue.resolved_at = now
    elif new_status == Issue.Status.REOPENED:
        issue.resolved_at = None
        issue.closed_at = None
    elif new_status == Issue.Status.CLOSED:
        issue.closed_at = timezone.now()
    issue.save(update_fields=["status", "response_at", "resolved_at", "closed_at", "updated_at"])
    IssueEvent.objects.create(issue=issue, actor=actor, from_status=old_status, to_status=new_status, note=note)
    from apps.sla.services import record_sla_response, record_sla_resolution
    if new_status == Issue.Status.IN_PROGRESS:
        record_sla_response(issue, now)
    elif new_status == Issue.Status.RESOLVED:
        record_sla_resolution(issue, now)
    from apps.audit.services import record_audit
    record_audit("issue.status_changed", actor=actor, entity=issue, context={"from": old_status, "to": new_status})
    return issue
