from django.db import transaction

from apps.audit.services import record_audit
from apps.notifications.models import Notification
from django.db.models import Case, Count, IntegerField, Q, Value, When
from .models import Assignment, RoutingRule
from apps.campus.models import Team
from apps.users.models import User
from apps.users.roles import UserRole
from apps.issues.models import Issue


@transaction.atomic
def route_issue(issue):
    """Select by explicit specificity, then lower priority_order, then stable PK."""
    caller_issue = issue
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    existing = Assignment.objects.filter(issue=issue).order_by("-created_at", "-pk").first()
    if existing:
        return existing
    if issue.assigned_team_id and issue.assigned_to_id:
        current = User.objects.filter(
            pk=issue.assigned_to_id, is_active=True, role=UserRole.TECHNICAL_STAFF,
            teams__id=issue.assigned_team_id,
        ).first()
        if current:
            return None
    specificity = sum((Case(When(**{f"{field}__isnull": False}, then=Value(1)), default=Value(0), output_field=IntegerField()) for field in ("category", "location", "issue_priority")), Value(0))
    rules = RoutingRule.objects.filter(active=True, target_team__is_active=True).filter(models_match(issue)).annotate(
        specificity=specificity
    ).select_related("target_team", "target_user").order_by("-specificity", "priority_order", "pk")
    rule = rules.first()
    if not rule:
        Assignment.objects.create(issue=issue, reason="No active routing rule matched", is_automatic=True)
        return None
    # Lock the destination team to serialize concurrent auto-assignment
    # decisions for that queue. Lock technician rows only; the M2M join itself
    # is not a lock target on PostgreSQL.
    team = Team.objects.select_for_update().get(pk=rule.target_team_id)
    if not team.is_active:
        Assignment.objects.create(issue=issue, reason="Matched team became inactive before assignment", routing_rule=rule, is_automatic=True)
        return None
    active_statuses = [issue.Status.OPEN, issue.Status.IN_REVIEW, issue.Status.ASSIGNED, issue.Status.IN_PROGRESS, issue.Status.REOPENED]
    technicians = list(User.objects.filter(
        is_active=True,
        role=UserRole.TECHNICAL_STAFF,
        teams=team,
    ).select_for_update(of=("self",)).order_by("pk"))
    technician_ids = [person.pk for person in technicians]
    issue_workload = dict(Issue.objects.filter(assigned_to_id__in=technician_ids, status__in=active_statuses)
                          .values("assigned_to_id").annotate(total=Count("pk")).values_list("assigned_to_id", "total"))
    from apps.workorders.models import WorkOrder
    work_order_workload = dict(WorkOrder.objects.filter(assigned_to_id__in=technician_ids, status__in=["ASSIGNED", "ACCEPTED", "IN_PROGRESS", "REWORK"])
                               .values("assigned_to_id").annotate(total=Count("pk")).values_list("assigned_to_id", "total"))
    selected = min(technicians, key=lambda person: (issue_workload.get(person.pk, 0), work_order_workload.get(person.pk, 0), person.pk), default=None)
    # A configured routing user may break a workload tie, but cannot bypass
    # least-workload selection or the active technical-team membership check.
    pinned = next((person for person in technicians if person.pk == rule.target_user_id), None)
    if pinned and (issue_workload.get(pinned.pk, 0), work_order_workload.get(pinned.pk, 0)) == (
        issue_workload.get(selected.pk, 0), work_order_workload.get(selected.pk, 0)
    ):
        selected = pinned
    issue.assigned_team = team
    issue.assigned_to = selected
    if issue.status == issue.Status.OPEN:
        from apps.issues.models import IssueEvent
        IssueEvent.objects.create(issue=issue, from_status=issue.Status.OPEN, to_status=issue.Status.ASSIGNED, note=f"Automatically assigned by rule: {rule.name}")
        issue.status = issue.Status.ASSIGNED
    issue.save(update_fields=["assigned_team", "assigned_to", "status", "updated_at"])
    caller_issue.__dict__.update(issue.__dict__)
    reason = f"Matched routing rule: {rule.name}"
    reason += f"; lowest active workload selected technician {selected.pk}" if selected else "; no eligible active technical staff; left in admin queue"
    assignment = Assignment.objects.create(issue=issue, team=team, user=selected, routing_rule=rule, is_automatic=True, reason=reason)
    recipients = [selected] if selected else User.objects.filter(role=UserRole.ADMIN, is_active=True)
    for recipient in recipients:
        Notification.objects.get_or_create(recipient=recipient, issue=issue, notification_type="ISSUE_ASSIGNED", defaults={"title": "Issue assigned" if selected else "Issue needs assignment", "message": f"{issue.ticket_number}: {issue.title}"})
    record_audit("issue.assigned" if selected else "issue.assignment_unavailable", entity=assignment, context={"issue_id": issue.pk, "team_id": team.pk, "technician_id": selected.pk if selected else None, "rule_id": rule.pk, "automatic": True})
    return assignment


def models_match(issue):
    routing_priority = getattr(issue, "routing_priority", None) or issue.priority
    return (Q(category__isnull=True) | Q(category=issue.category)) & (Q(location__isnull=True) | Q(location=issue.location)) & (Q(issue_priority__isnull=True) | Q(issue_priority=routing_priority))
