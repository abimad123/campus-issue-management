from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, Max, OuterRef, Q
from django.utils import timezone

from apps.audit.services import record_audit
from apps.notifications.models import Notification
from apps.users.models import User
from .models import SlaEscalationLevel, SlaEvent, SlaPolicy


def get_policy_for_issue(issue):
    policies = SlaPolicy.objects.filter(active=True).filter(
        Q(category__isnull=True) | Q(category=issue.category),
        Q(issue_priority__isnull=True) | Q(issue_priority=issue.priority),
    )
    return min(policies, key=lambda p: (-sum(v is not None for v in (p.category_id, p.issue_priority)), p.priority_order, p.pk), default=None)


def start_sla(issue):
    policy = get_policy_for_issue(issue)
    if not policy:
        return None
    now = issue.created_at or timezone.now()
    issue.sla_policy = policy
    issue.response_due_at = now + timedelta(seconds=policy.response_time_seconds)
    issue.resolution_due_at = now + timedelta(seconds=policy.resolution_time_seconds)
    issue.save(update_fields=["sla_policy", "response_due_at", "resolution_due_at", "updated_at"])
    SlaEvent.objects.get_or_create(issue=issue, event_type=SlaEvent.Type.STARTED, defaults={"policy": policy})
    return policy


def _notify(issue, role, kind, title, message):
    qs = User.objects.filter(is_active=True, role=role)
    if role == "SUPERVISOR" and issue.assigned_team_id:
        qs = qs.filter(teams=issue.assigned_team)
    for recipient in qs.distinct():
        Notification.objects.get_or_create(recipient=recipient, issue=issue, notification_type=kind, defaults={"title": title, "message": message})


def _record_breach(issue, condition, occurred_at):
    policy = issue.sla_policy
    field = "response_breached_at" if condition == "response" else "resolution_breached_at"
    event_type = SlaEvent.Type.RESPONSE_BREACHED if condition == "response" else SlaEvent.Type.RESOLUTION_BREACHED
    if getattr(issue, field):
        return False
    setattr(issue, field, occurred_at)
    update_fields = [field, "updated_at"]
    if issue.escalation_started_at is None:
        issue.escalation_started_at = occurred_at
        update_fields.append("escalation_started_at")
        next_level = SlaEscalationLevel.objects.filter(policy=policy, level__gt=issue.current_escalation_level).order_by("level").first()
        issue.next_escalation_at = occurred_at + timedelta(seconds=next_level.after_breach_seconds) if next_level else None
        update_fields.append("next_escalation_at")
    issue.save(update_fields=update_fields)
    _, created = SlaEvent.objects.get_or_create(issue=issue, event_type=event_type, defaults={"policy": policy, "created_at": occurred_at})
    if created:
        _notify(issue, "SUPERVISOR", f"{condition.upper()}_SLA_BREACHED", f"{condition.title()} SLA breached", issue.ticket_number)
        record_audit(f"sla.{condition}_breached", entity=issue, context={"policy_id": policy.pk})
    return created


def record_sla_response(issue, occurred_at):
    if issue.sla_policy_id and issue.response_due_at and occurred_at > issue.response_due_at:
        _record_breach(issue, "response", occurred_at)


def record_sla_resolution(issue, occurred_at):
    if issue.sla_policy_id and issue.resolution_due_at and occurred_at > issue.resolution_due_at:
        _record_breach(issue, "resolution", occurred_at)


@transaction.atomic
def process_sla_sweep(now=None, batch_size=500):
    """Idempotent bounded sweep; events/notifications are created once per issue condition."""
    now = now or timezone.now()
    from apps.issues.models import Issue
    max_warning = SlaPolicy.objects.aggregate(value=Max("warning_before_seconds"))["value"] or 0
    response_unresolved = Q(response_at__isnull=True) & ~Q(status__in=["IN_PROGRESS", "RESOLVED", "CLOSED"])
    response_due = Q(response_due_at__lte=now, response_breached_at__isnull=True)
    response_warning = Q(response_due_at__gt=now, response_due_at__lte=now + timedelta(seconds=max_warning), response_warning_exists=False)
    eligible = Issue.objects.filter(sla_policy__isnull=False).exclude(status__in=["RESOLVED", "CLOSED"]).annotate(
        response_warning_exists=Exists(SlaEvent.objects.filter(issue_id=OuterRef("pk"), event_type=SlaEvent.Type.RESPONSE_WARNING)),
        resolution_warning_exists=Exists(SlaEvent.objects.filter(issue_id=OuterRef("pk"), event_type=SlaEvent.Type.RESOLUTION_WARNING)),
    ).filter(
        (response_unresolved & (response_due | response_warning))
        | Q(resolution_due_at__lte=now, resolution_breached_at__isnull=True)
        | Q(resolution_due_at__gt=now, resolution_due_at__lte=now + timedelta(seconds=max_warning), resolution_warning_exists=False)
        | Q(next_escalation_at__lte=now)
    )
    issues = list(eligible.select_related("sla_policy", "assigned_team").select_for_update(of=("self",)).order_by("response_due_at", "pk")[:batch_size])
    processed = 0
    for issue in issues:
        policy = issue.sla_policy
        response_done = issue.response_at is not None or issue.status in {"IN_PROGRESS", "RESOLVED", "CLOSED"}
        if not response_done and issue.response_due_at and issue.response_due_at <= now:
            if not issue.response_breached_at:
                _record_breach(issue, "response", now)
        if not response_done and issue.response_due_at and issue.response_due_at - timedelta(seconds=policy.warning_before_seconds) <= now < issue.response_due_at:
            _, created = SlaEvent.objects.get_or_create(issue=issue, event_type=SlaEvent.Type.RESPONSE_WARNING, defaults={"policy": policy, "metadata": {"deadline": issue.response_due_at.isoformat(), "kind": "response"}})
            if created:
                _notify(issue, "SUPERVISOR", "RESPONSE_SLA_APPROACHING", "Response deadline approaching", issue.ticket_number)
        if issue.status not in {"RESOLVED", "CLOSED"} and issue.resolution_due_at and issue.resolution_due_at <= now and not issue.resolution_breached_at:
            _record_breach(issue, "resolution", now)
        if issue.status not in {"RESOLVED", "CLOSED"} and issue.resolution_due_at and issue.resolution_due_at - timedelta(seconds=policy.warning_before_seconds) <= now < issue.resolution_due_at:
            _, created = SlaEvent.objects.get_or_create(issue=issue, event_type=SlaEvent.Type.RESOLUTION_WARNING, defaults={"policy": policy, "metadata": {"deadline": issue.resolution_due_at.isoformat(), "kind": "resolution"}})
            if created:
                _notify(issue, "SUPERVISOR", "RESOLUTION_SLA_APPROACHING", "Resolution deadline approaching", issue.ticket_number)
        issue.save(update_fields=["response_breached_at", "resolution_breached_at", "updated_at"])
        if issue.next_escalation_at and issue.next_escalation_at <= now:
            next_level = SlaEscalationLevel.objects.filter(policy=policy, level__gt=issue.current_escalation_level).order_by("level").first()
            if next_level:
                issue.current_escalation_level = next_level.level
                SlaEvent.objects.create(issue=issue, policy=policy, event_type=SlaEvent.Type.ESCALATION, escalation_level=next_level.level, metadata={"recipient_role": next_level.recipient_role})
                _notify(issue, next_level.recipient_role, "ESCALATION_TRIGGERED", "Issue escalated", issue.ticket_number)
                record_audit("sla.escalation_triggered", entity=issue, context={"level": next_level.level, "recipient_role": next_level.recipient_role})
                following = SlaEscalationLevel.objects.filter(policy=policy, level__gt=next_level.level).order_by("level").first()
                issue.next_escalation_at = issue.escalation_started_at + timedelta(seconds=following.after_breach_seconds) if following else None
                issue.save(update_fields=["current_escalation_level", "next_escalation_at", "updated_at"])
        processed += 1
    return processed
