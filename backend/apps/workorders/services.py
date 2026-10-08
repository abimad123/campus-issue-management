from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import record_audit
from apps.campus.models import Team
from apps.issues.access import visible_issues_for
from apps.issues.models import Issue
from apps.notifications.models import Notification
from apps.users.roles import ISSUE_MANAGEMENT_ROLES, UserRole

from .models import WorkOrder, WorkOrderAssignment, WorkOrderEvent, WorkOrderMaterial, WorkOrderNote

MANAGER_ROLES = ISSUE_MANAGEMENT_ROLES | {UserRole.SUPERVISOR}


def visible_work_orders_for(user):
    queryset = WorkOrder.objects.all()
    if user.role in ISSUE_MANAGEMENT_ROLES:
        return queryset
    if user.role == UserRole.SUPERVISOR:
        return queryset.filter(team__in=user.teams.filter(is_active=True)).distinct()
    if user.role == UserRole.TECHNICIAN:
        return queryset.filter(assigned_to=user, assigned_to__is_active=True)
    return queryset.none()


def get_visible_work_order(user, pk, *, lock=False):
    work_order_id = visible_work_orders_for(user).filter(pk=pk).values_list("pk", flat=True).first()
    if work_order_id is None:
        raise NotFound()
    queryset = WorkOrder.objects.select_related("issue", "team", "assigned_to", "created_by", "completed_by", "verified_by")
    if lock:
        queryset = queryset.select_for_update(of=("self",))
    return queryset.get(pk=work_order_id)


def can_manage(user, work_order):
    if user.role in ISSUE_MANAGEMENT_ROLES:
        return True
    return user.role == UserRole.SUPERVISOR and user.teams.filter(pk=work_order.team_id, is_active=True).exists()


def require_manager(user, work_order):
    if not can_manage(user, work_order):
        raise PermissionDenied("You are not authorized to manage this work order.")


def require_technician(user, work_order):
    if user.role != UserRole.TECHNICIAN or work_order.assigned_to_id != user.pk or not user.is_active:
        raise PermissionDenied("Only the active assigned technician may perform this action.")


def _event(work_order, actor, event_type, *, old_status="", note=""):
    WorkOrderEvent.objects.create(
        work_order=work_order, actor=actor, event_type=event_type,
        from_status=old_status, to_status=work_order.status, note=note,
    )
    record_audit(
        f"work_order.{event_type.lower()}", actor=actor, entity=work_order,
        context={"issue_id": work_order.issue_id, "work_order_number": work_order.number, "status": work_order.status, "note": note},
    )


def _notify(user, work_order, kind, title, message):
    if user and user.is_active:
        Notification.objects.create(
            recipient=user, issue=work_order.issue, notification_type=kind,
            title=title, message=message[:500],
        )


def _notify_supervisors(work_order, kind, title, message):
    for supervisor in work_order.team.members.filter(role=UserRole.SUPERVISOR, is_active=True).distinct():
        _notify(supervisor, work_order, kind, title, message)


@transaction.atomic
def create_work_order(*, issue, actor, team, title=None, instructions=""):
    if actor.role not in MANAGER_ROLES:
        raise PermissionDenied("Only operational staff may create work orders.")
    if not visible_issues_for(actor).filter(pk=issue.pk).exists():
        raise NotFound()
    if not team.is_active:
        raise ValidationError({"team": "Choose an active team."})
    if actor.role == UserRole.SUPERVISOR and not actor.teams.filter(pk=team.pk, is_active=True).exists():
        raise PermissionDenied("Supervisors may create work orders only for their own teams.")
    if issue.assigned_team_id and team.pk != issue.assigned_team_id and actor.role == UserRole.SUPERVISOR:
        raise PermissionDenied("The work order team must match the issue's assigned team.")
    work_order = WorkOrder.objects.create(
        issue=issue, team=team, title=title or issue.title,
        instructions=instructions, priority=issue.priority, created_by=actor,
    )
    WorkOrderAssignment.objects.create(work_order=work_order, team=team, assigned_by=actor, reason="Work order created")
    _event(work_order, actor, "CREATED", note=f"Created from {issue.ticket_number}")
    _notify_supervisors(work_order, "WORK_ORDER_CREATED", "Work order needs assignment", work_order.number)
    return work_order


@transaction.atomic
def assign_work_order(*, work_order, actor, team, technician, reason):
    require_manager(actor, work_order)
    if work_order.status not in {WorkOrder.Status.ASSIGNED, WorkOrder.Status.ACCEPTED, WorkOrder.Status.REWORK}:
        raise ValidationError({"status": "Only unstarted or returned work orders can be assigned or reassigned."})
    if not team.is_active:
        raise ValidationError({"team": "Choose an active team."})
    if actor.role == UserRole.SUPERVISOR and not actor.teams.filter(pk=team.pk, is_active=True).exists():
        raise PermissionDenied("Supervisors may assign work only within their own teams.")
    if team.pk != work_order.team_id and actor.role == UserRole.SUPERVISOR:
        raise PermissionDenied("Supervisors may not move work orders outside their current team scope.")
    if technician and (technician.role != UserRole.TECHNICIAN or not technician.is_active or not team.members.filter(pk=technician.pk).exists()):
        raise ValidationError({"technician": "Choose an active technician who belongs to the selected team."})
    old_technician = work_order.assigned_to
    old_team = work_order.team
    old_status = work_order.status
    work_order.team = team
    work_order.assigned_to = technician
    if old_status in {WorkOrder.Status.ACCEPTED, WorkOrder.Status.REWORK}:
        work_order.status = WorkOrder.Status.ASSIGNED
        work_order.accepted_at = None
        work_order.rework_reason = ""
    work_order.save(update_fields=["team", "assigned_to", "status", "accepted_at", "rework_reason", "updated_at"])
    WorkOrderAssignment.objects.create(work_order=work_order, team=team, technician=technician, assigned_by=actor, reason=reason)
    _event(work_order, actor, "REASSIGNED" if old_technician or old_team.pk != team.pk else "ASSIGNED", old_status=old_status, note=reason)
    _notify(old_technician, work_order, "WORK_ORDER_REASSIGNED", "Work order reassigned", work_order.number)
    _notify(technician, work_order, "WORK_ORDER_ASSIGNED", "Work order assigned to you", f"{work_order.number}: {work_order.title}")
    return work_order


def _transition(work_order, actor, target, event_type, *, note="", allowed_from=()):
    if work_order.status not in allowed_from:
        raise ValidationError({"status": f"Cannot move a {work_order.status.lower().replace('_', ' ')} work order to {target.lower().replace('_', ' ')}."})
    old_status = work_order.status
    work_order.status = target
    work_order.save(update_fields=["status", "updated_at"])
    _event(work_order, actor, event_type, old_status=old_status, note=note)


@transaction.atomic
def accept_work_order(*, work_order, actor):
    require_technician(actor, work_order)
    if work_order.status != WorkOrder.Status.ASSIGNED:
        raise ValidationError({"status": "Only assigned work orders can be accepted."})
    work_order.accepted_at = timezone.now()
    work_order.save(update_fields=["accepted_at", "updated_at"])
    _transition(work_order, actor, WorkOrder.Status.ACCEPTED, "ACCEPTED", allowed_from=(WorkOrder.Status.ASSIGNED,))
    _notify_supervisors(work_order, "WORK_ORDER_ACCEPTED", "Work order accepted", work_order.number)
    return work_order


@transaction.atomic
def start_work_order(*, work_order, actor):
    require_technician(actor, work_order)
    now = timezone.now()
    _transition(work_order, actor, WorkOrder.Status.IN_PROGRESS, "STARTED", note="Field work started", allowed_from=(WorkOrder.Status.ACCEPTED, WorkOrder.Status.REWORK))
    work_order.started_at = work_order.started_at or now
    work_order.save(update_fields=["started_at", "updated_at"])
    _notify_supervisors(work_order, "WORK_ORDER_STARTED", "Field work started", work_order.number)
    return work_order


@transaction.atomic
def add_note(*, work_order, actor, body):
    if actor.role == UserRole.TECHNICIAN:
        require_technician(actor, work_order)
    else:
        require_manager(actor, work_order)
    if work_order.status in {WorkOrder.Status.COMPLETED, WorkOrder.Status.VERIFIED, WorkOrder.Status.CLOSED, WorkOrder.Status.CANCELLED}:
        raise ValidationError({"status": "Notes cannot be added after work is complete."})
    note = WorkOrderNote.objects.create(work_order=work_order, author=actor, body=body)
    _event(work_order, actor, "NOTE_ADDED", note="Technician note added" if actor.role == UserRole.TECHNICIAN else "Operational note added")
    return note


@transaction.atomic
def add_material(*, work_order, actor, name, quantity, note=""):
    require_technician(actor, work_order)
    if work_order.status != WorkOrder.Status.IN_PROGRESS:
        raise ValidationError({"status": "Materials can be recorded while work is in progress."})
    material = WorkOrderMaterial.objects.create(work_order=work_order, recorded_by=actor, name=name, quantity=quantity, note=note)
    _event(work_order, actor, "MATERIAL_RECORDED", note=f"Recorded material: {name}")
    return material


@transaction.atomic
def complete_work_order(*, work_order, actor, resolution_summary):
    require_technician(actor, work_order)
    if work_order.status != WorkOrder.Status.IN_PROGRESS:
        raise ValidationError({"status": "Only in-progress work orders can be completed."})
    if len(resolution_summary.strip()) < 20:
        raise ValidationError({"resolution_summary": "Provide at least 20 characters describing the work performed and resulting condition."})
    now = timezone.now()
    work_order.resolution_summary = resolution_summary.strip()
    work_order.completed_by = actor
    work_order.completed_at = now
    work_order.status = WorkOrder.Status.COMPLETED
    work_order.save(update_fields=["resolution_summary", "completed_by", "completed_at", "status", "updated_at"])
    _event(work_order, actor, "COMPLETED", old_status=WorkOrder.Status.IN_PROGRESS, note="Submitted for supervisor verification")
    _notify_supervisors(work_order, "WORK_ORDER_AWAITING_VERIFICATION", "Work order ready for review", work_order.number)
    return work_order


@transaction.atomic
def verify_work_order(*, work_order, actor):
    require_manager(actor, work_order)
    if work_order.status != WorkOrder.Status.COMPLETED:
        raise ValidationError({"status": "Only completed work orders can be verified."})
    now = timezone.now()
    work_order.status = WorkOrder.Status.VERIFIED
    work_order.verified_by = actor
    work_order.verified_at = now
    work_order.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
    _event(work_order, actor, "VERIFIED", old_status=WorkOrder.Status.COMPLETED, note="Supervisor verified field completion")
    if work_order.issue.status == Issue.Status.IN_PROGRESS and (
        actor.role in ISSUE_MANAGEMENT_ROLES or actor.teams.filter(pk=work_order.issue.assigned_team_id, is_active=True).exists()
    ):
        from apps.issues.services import transition_issue
        transition_issue(work_order.issue, new_status=Issue.Status.RESOLVED, actor=actor, note=f"Resolved after verification of {work_order.number}")
    _notify(work_order.assigned_to, work_order, "WORK_ORDER_VERIFIED", "Work order verified", work_order.number)
    return work_order


@transaction.atomic
def reject_work_order(*, work_order, actor, reason):
    require_manager(actor, work_order)
    if work_order.status != WorkOrder.Status.COMPLETED:
        raise ValidationError({"status": "Only completed work can be returned for rework."})
    work_order.rework_reason = reason
    work_order.status = WorkOrder.Status.REWORK
    work_order.completed_at = None
    work_order.completed_by = None
    work_order.save(update_fields=["rework_reason", "status", "completed_at", "completed_by", "updated_at"])
    _event(work_order, actor, "REWORK_REQUESTED", old_status=WorkOrder.Status.COMPLETED, note=reason)
    _notify(work_order.assigned_to, work_order, "WORK_ORDER_REWORK", "Additional work requested", reason)
    return work_order


@transaction.atomic
def cancel_work_order(*, work_order, actor, reason):
    require_manager(actor, work_order)
    _transition(work_order, actor, WorkOrder.Status.CANCELLED, "CANCELLED", note=reason, allowed_from=(WorkOrder.Status.ASSIGNED, WorkOrder.Status.ACCEPTED, WorkOrder.Status.REWORK))
    work_order.cancellation_reason = reason
    work_order.save(update_fields=["cancellation_reason", "updated_at"])
    _notify(work_order.assigned_to, work_order, "WORK_ORDER_CANCELLED", "Work order cancelled", reason)
    return work_order


@transaction.atomic
def close_work_order(*, work_order, actor):
    require_manager(actor, work_order)
    _transition(work_order, actor, WorkOrder.Status.CLOSED, "CLOSED", note="Work order closed after verification", allowed_from=(WorkOrder.Status.VERIFIED,))
    work_order.closed_at = timezone.now()
    work_order.save(update_fields=["closed_at", "updated_at"])
    return work_order
