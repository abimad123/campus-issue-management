from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from apps.campus.models import Campus, Building, Location, Team
from apps.issues.models import Issue, IssueCategory
from apps.users.models import User
from apps.users.roles import UserRole
from .models import Assignment, RoutingRule
from .services import route_issue
from apps.sla.models import SlaPolicy, SlaEvent, SlaEscalationLevel
from apps.sla.services import get_policy_for_issue, process_sla_sweep
from apps.sla.services import start_sla
from apps.notifications.models import Notification
from apps.audit.models import AuditEntry
from django.utils import timezone
from datetime import timedelta
from apps.issues.services import transition_issue


class RoutingAndSlaTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin@tests.test", "Admin", "test-password", role=UserRole.ADMIN)
        self.student = User.objects.create_user("student@tests.test", "Student", "test-password", role=UserRole.STUDENT)
        self.supervisor = User.objects.create_user("supervisor@tests.test", "Supervisor", "test-password", role=UserRole.ADMIN)
        campus = Campus.objects.create(name="Test", code="test")
        building = Building.objects.create(campus=campus, name="Block", code="block")
        self.location = Location.objects.create(building=building, name="Room")
        self.category = IssueCategory.objects.create(name="Network")
        self.team = Team.objects.create(name="Network Operations")
        self.team.members.add(self.supervisor)
        self.issue = Issue.objects.create(title="Wi-Fi access unavailable", description="Wireless connectivity is unavailable in this room.", category=self.category, location=self.location, reporter=self.student, priority=Issue.Priority.HIGH)

    def test_routing_specificity_precedence_and_inactive_rule(self):
        fallback = RoutingRule.objects.create(name="Category", category=self.category, target_team=self.team, priority_order=1)
        specific_team = Team.objects.create(name="Room Response")
        RoutingRule.objects.create(name="Exact", category=self.category, location=self.location, issue_priority="HIGH", target_team=specific_team, priority_order=50)
        RoutingRule.objects.create(name="Disabled", category=self.category, location=self.location, issue_priority="HIGH", target_team=self.team, priority_order=0, active=False)
        assignment = route_issue(self.issue)
        self.assertEqual(assignment.routing_rule.name, "Exact")
        self.assertEqual(self.issue.assigned_team, specific_team)
        self.assertEqual(Assignment.objects.filter(issue=self.issue).count(), 1)
        self.assertNotEqual(fallback.pk, assignment.routing_rule_id)

    def test_no_rule_leaves_unassigned_and_records_outcome(self):
        self.assertIsNone(route_issue(self.issue))
        self.issue.refresh_from_db()
        self.assertIsNone(self.issue.assigned_team)
        self.assertTrue(self.issue.assignments.get().is_automatic)

    def test_automatic_assignment_uses_lowest_active_issue_workload_and_valid_team_members(self):
        from apps.workorders.models import WorkOrder

        first = User.objects.create_user("first-tech@tests.test", "First Technician", "test-password", role=UserRole.TECHNICAL_STAFF)
        second = User.objects.create_user("second-tech@tests.test", "Second Technician", "test-password", role=UserRole.TECHNICAL_STAFF)
        inactive = User.objects.create_user("inactive-tech@tests.test", "Inactive Technician", "test-password", role=UserRole.TECHNICAL_STAFF, is_active=False)
        outside = User.objects.create_user("outside-tech@tests.test", "Outside Technician", "test-password", role=UserRole.TECHNICAL_STAFF)
        self.team.members.add(first, second, inactive)
        RoutingRule.objects.create(name="Automatic Network Team", category=self.category, target_team=self.team, target_user=first)
        Issue.objects.create(title="First active issue", description="An active issue already assigned to the first technician.", category=self.category, location=self.location, reporter=self.student, assigned_team=self.team, assigned_to=first, status=Issue.Status.IN_PROGRESS)
        Issue.objects.create(title="Second active issue", description="A second active issue already assigned to the first technician.", category=self.category, location=self.location, reporter=self.student, assigned_team=self.team, assigned_to=first, status=Issue.Status.ASSIGNED)
        WorkOrder.objects.create(issue=self.issue, team=self.team, assigned_to=second, title="Existing field task")

        assignment = route_issue(self.issue)
        self.assertEqual(assignment.user, second)
        self.assertEqual(assignment.team, self.team)
        self.assertIn("lowest active workload", assignment.reason)
        self.assertNotEqual(assignment.user, inactive)
        self.assertNotEqual(assignment.user, outside)

    def test_no_eligible_technical_staff_leaves_issue_in_admin_queue(self):
        inactive = User.objects.create_user("inactive-only@tests.test", "Inactive Only", "test-password", role=UserRole.TECHNICAL_STAFF, is_active=False)
        self.team.members.add(inactive)
        RoutingRule.objects.create(name="No Active Technician", category=self.category, target_team=self.team)
        assignment = route_issue(self.issue)
        self.issue.refresh_from_db()
        self.assertIsNone(assignment.user)
        self.assertIsNone(self.issue.assigned_to)
        self.assertEqual(self.issue.assigned_team, self.team)
        self.assertTrue(Notification.objects.filter(issue=self.issue, recipient=self.admin, notification_type="ISSUE_ASSIGNED").exists())

    def test_policy_precedence_default_and_deadlines_persist(self):
        default = SlaPolicy.objects.create(name="Default", response_time_seconds=900, resolution_time_seconds=3600)
        SlaPolicy.objects.create(name="High priority", issue_priority="HIGH", response_time_seconds=300, resolution_time_seconds=1200)
        self.assertEqual(get_policy_for_issue(self.issue).name, "High priority")
        self.issue.sla_policy = get_policy_for_issue(self.issue)
        self.issue.response_due_at = self.issue.created_at + timedelta(seconds=300)
        self.issue.resolution_due_at = self.issue.created_at + timedelta(seconds=1200)
        self.issue.save()
        self.issue.refresh_from_db()
        self.assertIsNotNone(self.issue.response_due_at)
        self.assertEqual(default.name, "Default")

    def test_issue_submission_runs_routing_and_sla_workflow_atomically(self):
        from django.urls import reverse
        from rest_framework.test import APIClient
        from apps.issues.models import IssueEvent
        RoutingRule.objects.create(name="Network team", category=self.category, target_team=self.team)
        policy = SlaPolicy.objects.create(name="Network normal", category=self.category, issue_priority="MEDIUM", response_time_seconds=600, resolution_time_seconds=3600)
        SlaPolicy.objects.create(name="Network high priority", category=self.category, issue_priority="HIGH", response_time_seconds=60, resolution_time_seconds=300)
        client = APIClient()
        staff = User.objects.create_user("staff-priority@tests.test", "Staff Requester", "test-password", role=UserRole.STAFF)
        client.force_authenticate(staff)
        technician = User.objects.create_user("workflow-tech@tests.test", "Workflow Technician", "test-password", role=UserRole.TECHNICAL_STAFF)
        self.team.members.add(technician)
        response = client.post(reverse("issue-list"), {"title": "Wi-Fi not available", "description": "Wireless service has stopped working in this location.", "category": self.category.pk, "location": self.location.pk, "request_priority": True, "priority_reason": "Classes cannot access course materials."}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        issue = Issue.objects.get(pk=response.data["id"])
        self.assertEqual(issue.assigned_team, self.team)
        self.assertEqual(issue.sla_policy, policy)
        self.assertEqual(issue.priority, Issue.Priority.HIGH)
        self.assertEqual(issue.routing_priority, Issue.Priority.MEDIUM)
        self.assertAlmostEqual((issue.response_due_at - issue.created_at).total_seconds(), 600, delta=2)
        self.assertEqual(issue.sla_events.filter(event_type=SlaEvent.Type.STARTED).count(), 1)
        self.assertTrue(issue.assignments.get().is_automatic)
        self.assertTrue(Notification.objects.filter(issue=issue, recipient=technician, notification_type="ISSUE_ASSIGNED").exists())
        self.assertTrue(AuditEntry.objects.filter(action="issue.assigned", context__issue_id=issue.pk).exists())
        self.assertEqual(IssueEvent.objects.filter(issue=issue).count(), 2)

    def test_start_policy_deadline_stays_after_object_reload(self):
        policy = SlaPolicy.objects.create(name="Default", response_time_seconds=240, resolution_time_seconds=1800)
        selected = start_sla(self.issue)
        self.assertEqual(selected, policy)
        stored_response = self.issue.response_due_at
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.response_due_at, stored_response)
        self.assertEqual((self.issue.resolution_due_at - self.issue.created_at).total_seconds(), 1800)

    def test_sweep_warns_breaches_escalates_once_and_notifies(self):
        policy = SlaPolicy.objects.create(name="Urgent", issue_priority="HIGH", response_time_seconds=60, resolution_time_seconds=120, warning_before_seconds=30)
        SlaEscalationLevel.objects.create(policy=policy, level=1, after_breach_seconds=0, recipient_role=UserRole.ADMIN)
        self.issue.sla_policy = policy
        self.issue.response_due_at = timezone.now() - timedelta(minutes=1)
        self.issue.resolution_due_at = timezone.now() - timedelta(seconds=30)
        self.issue.save()
        process_sla_sweep()
        process_sla_sweep()
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESPONSE_BREACHED).count(), 1)
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESOLUTION_BREACHED).count(), 1)
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.ESCALATION).count(), 1)
        self.assertEqual(self.issue.current_escalation_level, 1)
        self.assertEqual(Notification.objects.filter(issue=self.issue).values("notification_type").distinct().count(), 3)
        self.assertGreaterEqual(AuditEntry.objects.filter(action__startswith="sla.").count(), 3)

    def test_approaching_deadlines_warn_once_each(self):
        policy = SlaPolicy.objects.create(name="Warning", response_time_seconds=600, resolution_time_seconds=1200, warning_before_seconds=120)
        self.issue.sla_policy = policy
        self.issue.response_due_at = timezone.now() + timedelta(seconds=60)
        self.issue.resolution_due_at = timezone.now() + timedelta(seconds=90)
        self.issue.save()
        process_sla_sweep()
        process_sla_sweep()
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESPONSE_WARNING).count(), 1)
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESOLUTION_WARNING).count(), 1)
        self.assertEqual(Notification.objects.filter(issue=self.issue, notification_type__contains="APPROACHING").values("notification_type").distinct().count(), 2)

    def test_late_response_and_resolution_are_recorded_during_transitions(self):
        policy = SlaPolicy.objects.create(name="Transition test", response_time_seconds=60, resolution_time_seconds=120)
        self.issue.sla_policy = policy
        self.issue.response_due_at = timezone.now() - timedelta(minutes=5)
        self.issue.resolution_due_at = timezone.now() - timedelta(minutes=2)
        self.issue.status = Issue.Status.ASSIGNED
        self.issue.save()
        transition_issue(self.issue, new_status=Issue.Status.IN_PROGRESS, actor=self.admin)
        self.assertIsNotNone(self.issue.response_at)
        self.assertIsNotNone(self.issue.response_breached_at)
        transition_issue(self.issue, new_status=Issue.Status.RESOLVED, actor=self.admin)
        self.assertIsNotNone(self.issue.resolved_at)
        self.assertIsNotNone(self.issue.resolution_breached_at)
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESPONSE_BREACHED).count(), 1)
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESOLUTION_BREACHED).count(), 1)

    def _resolve_issue_with_sla(self, *, due_response, due_resolution, response_at=None, response_breached_at=None, resolution_breached_at=None):
        policy = SlaPolicy.objects.create(name=f"Reopen policy {SlaPolicy.objects.count()}", response_time_seconds=300, resolution_time_seconds=900, warning_before_seconds=30)
        self.issue.sla_policy = policy
        self.issue.response_due_at = due_response
        self.issue.resolution_due_at = due_resolution
        self.issue.response_at = response_at
        self.issue.response_breached_at = response_breached_at
        self.issue.resolution_breached_at = resolution_breached_at
        self.issue.status = Issue.Status.RESOLVED
        self.issue.resolved_at = timezone.now() - timedelta(minutes=1)
        self.issue.save()
        return policy

    def test_reopen_before_deadlines_keeps_original_sla_clock_without_breach(self):
        now = timezone.now()
        response_due = now + timedelta(hours=2)
        resolution_due = now + timedelta(hours=4)
        self._resolve_issue_with_sla(due_response=response_due, due_resolution=resolution_due, response_at=now - timedelta(minutes=2))
        transition_issue(self.issue, new_status=Issue.Status.REOPENED, actor=self.admin)

        process_sla_sweep(now=now)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.response_due_at, response_due)
        self.assertEqual(self.issue.resolution_due_at, resolution_due)
        self.assertIsNone(self.issue.response_breached_at)
        self.assertIsNone(self.issue.resolution_breached_at)
        self.assertFalse(self.issue.sla_events.filter(event_type__in=[SlaEvent.Type.RESPONSE_BREACHED, SlaEvent.Type.RESOLUTION_BREACHED]).exists())

    def test_reopen_after_deadline_breaches_only_unresolved_original_sla_once(self):
        now = timezone.now()
        response_due = now - timedelta(hours=2)
        resolution_due = now - timedelta(minutes=2)
        self._resolve_issue_with_sla(due_response=response_due, due_resolution=resolution_due, response_at=response_due - timedelta(minutes=1))
        transition_issue(self.issue, new_status=Issue.Status.REOPENED, actor=self.admin)

        process_sla_sweep(now=now)
        process_sla_sweep(now=now + timedelta(seconds=1))
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.response_due_at, response_due)
        self.assertEqual(self.issue.resolution_due_at, resolution_due)
        self.assertIsNone(self.issue.response_breached_at)
        self.assertIsNotNone(self.issue.resolution_breached_at)
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESPONSE_BREACHED).count(), 0)
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESOLUTION_BREACHED).count(), 1)
        self.assertEqual(Notification.objects.filter(issue=self.issue, notification_type="RESOLUTION_SLA_BREACHED").values("recipient").distinct().count(), 2)

    def test_reopen_preserves_existing_breaches_escalation_and_history(self):
        now = timezone.now()
        response_breach = now - timedelta(hours=3)
        resolution_breach = now - timedelta(hours=2)
        policy = self._resolve_issue_with_sla(
            due_response=now - timedelta(hours=4), due_resolution=now - timedelta(hours=3),
            response_at=now - timedelta(hours=3, minutes=30), response_breached_at=response_breach,
            resolution_breached_at=resolution_breach,
        )
        self.issue.current_escalation_level = 1
        self.issue.escalation_started_at = response_breach
        self.issue.next_escalation_at = now + timedelta(hours=1)
        self.issue.save(update_fields=["current_escalation_level", "escalation_started_at", "next_escalation_at"])
        SlaEvent.objects.create(issue=self.issue, policy=policy, event_type=SlaEvent.Type.RESPONSE_BREACHED, created_at=response_breach)
        SlaEvent.objects.create(issue=self.issue, policy=policy, event_type=SlaEvent.Type.RESOLUTION_BREACHED, created_at=resolution_breach)
        for event_type in ("RESPONSE_SLA_BREACHED", "RESOLUTION_SLA_BREACHED"):
            Notification.objects.create(recipient=self.supervisor, issue=self.issue, notification_type=event_type, title="Prior breach", message=self.issue.ticket_number)

        transition_issue(self.issue, new_status=Issue.Status.REOPENED, actor=self.admin)
        process_sla_sweep(now=now)
        process_sla_sweep(now=now + timedelta(seconds=1))
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.response_breached_at, response_breach)
        self.assertEqual(self.issue.resolution_breached_at, resolution_breach)
        self.assertEqual(self.issue.current_escalation_level, 1)
        self.assertEqual(self.issue.next_escalation_at, now + timedelta(hours=1))
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESPONSE_BREACHED).count(), 1)
        self.assertEqual(self.issue.sla_events.filter(event_type=SlaEvent.Type.RESOLUTION_BREACHED).count(), 1)
        self.assertEqual(Notification.objects.filter(issue=self.issue, notification_type__in=["RESPONSE_SLA_BREACHED", "RESOLUTION_SLA_BREACHED"]).values("notification_type").distinct().count(), 2)

    def test_operational_dashboard_counts_persisted_records(self):
        policy = SlaPolicy.objects.create(name="Dashboard", response_time_seconds=300, resolution_time_seconds=1200)
        self.issue.sla_policy = policy
        self.issue.response_due_at = timezone.now() + timedelta(minutes=2)
        self.issue.resolution_due_at = timezone.now() + timedelta(minutes=10)
        self.issue.save()
        SlaEvent.objects.create(issue=self.issue, policy=policy, event_type=SlaEvent.Type.RESPONSE_WARNING)
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get("/api/issues/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["open"], 1)
        self.assertEqual(response.data["at_risk"], 1)
        self.assertEqual(response.data["unassigned"], 1)

    def test_configuration_permissions_and_manual_assignment(self):
        client = APIClient()
        client.force_authenticate(self.student)
        self.assertEqual(client.post("/api/admin/routing-rules/", {"name": "x", "target_team": self.team.pk}, format="json").status_code, 403)
        self.assertEqual(client.post("/api/admin/sla-policies/", {"name": "x", "response_time_seconds": 20, "resolution_time_seconds": 30}, format="json").status_code, 403)
        self.assertEqual(client.post(f"/api/issues/{self.issue.pk}/assign/", {"team": self.team.pk, "reason": "route correction"}, format="json").status_code, 403)
        client.force_authenticate(self.student)
        denied = client.post(f"/api/issues/{self.issue.pk}/assign/", {"team": self.team.pk, "reason": "not permitted"}, format="json")
        self.assertEqual(denied.status_code, 403, denied.data)
        technician = User.objects.create_user("technician@tests.test", "Technician", "test-password", role=UserRole.TECHNICAL_STAFF)
        self.team.members.add(technician)
        client.force_authenticate(self.supervisor)
        outside_team = Team.objects.create(name="Other team")
        denied = client.post(f"/api/issues/{self.issue.pk}/assign/", {"team": outside_team.pk, "user": technician.pk, "reason": "invalid team membership"}, format="json")
        self.assertEqual(denied.status_code, 400)
        response = client.post(f"/api/issues/{self.issue.pk}/assign/", {"team": self.team.pk, "user": technician.pk, "reason": "admin assignment"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        client.force_authenticate(self.admin)
        response = client.post("/api/admin/sla-policies/", {"name": "Default policy", "response_time_seconds": 300, "resolution_time_seconds": 1800, "warning_before_seconds": 30, "escalation_levels": [{"level": 1, "after_breach_seconds": 0, "recipient_role": "ADMIN"}]}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
