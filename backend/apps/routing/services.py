from django.db import transaction

from apps.audit.services import record_audit
from apps.notifications.models import Notification
from django.db.models import Case, IntegerField, Q, Value, When
from .models import Assignment, RoutingRule


@transaction.atomic
def route_issue(issue):
    """Select by explicit specificity, then lower priority_order, then stable PK."""
    specificity = sum((Case(When(**{f"{field}__isnull": False}, then=Value(1)), default=Value(0), output_field=IntegerField()) for field in ("category", "location", "issue_priority")), Value(0))
    rules = RoutingRule.objects.filter(active=True, target_team__is_active=True).filter(models_match(issue)).annotate(
        specificity=specificity
    ).select_related("target_team", "target_user").order_by("-specificity", "priority_order", "pk")
    rule = rules.first()
    if not rule:
        Assignment.objects.create(issue=issue, reason="No active routing rule matched", is_automatic=True)
        return None
    issue.assigned_team = rule.target_team
    issue.assigned_to = rule.target_user
    if issue.status == issue.Status.OPEN:
        from apps.issues.models import IssueEvent
        IssueEvent.objects.create(issue=issue, from_status=issue.Status.OPEN, to_status=issue.Status.ASSIGNED, note=f"Automatically assigned by rule: {rule.name}")
        issue.status = issue.Status.ASSIGNED
    issue.save(update_fields=["assigned_team", "assigned_to", "status", "updated_at"])
    assignment = Assignment.objects.create(issue=issue, team=rule.target_team, user=rule.target_user, routing_rule=rule, is_automatic=True, reason=f"Matched routing rule: {rule.name}")
    for recipient in rule.target_team.members.filter(is_active=True):
        Notification.objects.create(recipient=recipient, issue=issue, notification_type="ISSUE_ASSIGNED", title="Issue assigned to your team", message=f"{issue.ticket_number}: {issue.title}")
    record_audit("issue.assigned", entity=assignment, context={"issue_id": issue.pk, "team_id": rule.target_team_id, "rule_id": rule.pk, "automatic": True})
    return assignment


def models_match(issue):
    return (Q(category__isnull=True) | Q(category=issue.category)) & (Q(location__isnull=True) | Q(location=issue.location)) & (Q(issue_priority__isnull=True) | Q(issue_priority=issue.priority))
