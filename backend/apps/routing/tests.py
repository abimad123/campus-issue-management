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


class RoutingAndSlaTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin@tests.test", "Admin", "test-password", role=UserRole.CAMPUS_ADMIN)
        self.student = User.objects.create_user("student@tests.test", "Student", "test-password", role=UserRole.STUDENT)
        self.supervisor = User.objects.create_user("supervisor@tests.test", "Supervisor", "test-password", role=UserRole.SUPERVISOR)
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
        policy = SlaPolicy.objects.create(name="Network high", category=self.category, issue_priority="HIGH", response_time_seconds=600, resolution_time_seconds=3600)
        client = APIClient()
        client.force_authenticate(self.student)
        response = client.post(reverse("issue-list"), {"title": "Wi-Fi not available", "description": "Wireless service has stopped working in this location.", "category": self.category.pk, "location": self.location.pk, "priority": "HIGH"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        issue = Issue.objects.get(pk=response.data["id"])
        self.assertEqual(issue.assigned_team, self.team)
        self.assertEqual(issue.sla_policy, policy)
        self.assertAlmostEqual((issue.response_due_at - issue.created_at).total_seconds(), 600, delta=2)
        self.assertEqual(issue.sla_events.filter(event_type=SlaEvent.Type.STARTED).count(), 1)
        self.assertTrue(issue.assignments.get().is_automatic)
        self.assertTrue(Notification.objects.filter(issue=issue, recipient=self.supervisor, notification_type="ISSUE_ASSIGNED").exists())
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
        SlaEscalationLevel.objects.create(policy=policy, level=1, after_breach_seconds=0, recipient_role=UserRole.SUPERVISOR)
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
        self.assertEqual(Notification.objects.filter(issue=self.issue).count(), 3)
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
        self.assertEqual(Notification.objects.filter(issue=self.issue, notification_type__contains="APPROACHING").count(), 2)

    def test_late_response_and_resolution_are_recorded_during_transitions(self):
        from apps.issues.services import transition_issue
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
        client.force_authenticate(self.supervisor)
        response = client.post(f"/api/issues/{self.issue.pk}/assign/", {"team": self.team.pk, "reason": "team scope"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        client.force_authenticate(self.admin)
        response = client.post("/api/admin/sla-policies/", {"name": "Default policy", "response_time_seconds": 300, "resolution_time_seconds": 1800, "warning_before_seconds": 30, "escalation_levels": [{"level": 1, "after_breach_seconds": 0, "recipient_role": "SUPERVISOR"}]}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
