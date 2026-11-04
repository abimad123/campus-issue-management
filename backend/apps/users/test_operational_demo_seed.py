from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.issues.models import Issue
from apps.routing.models import Assignment, RoutingRule
from apps.sla.models import SlaEvent, SlaPolicy
from apps.users.models import User
from apps.users.roles import UserRole
from apps.workorders.models import WorkOrder


class OperationalDemoSeedCommandTests(TestCase):
    def test_operational_seed_is_idempotent_and_preserves_existing_passwords(self):
        with patch("apps.users.management.commands.seed_development.getpass", return_value="Development-Only-Password-2026!"):
            call_command("seed_development", stdout=StringIO())
        with patch("apps.users.management.commands.seed_operational_demo.getpass", return_value="Development-Only-Password-2026!"):
            call_command("seed_operational_demo", stdout=StringIO())

        demo_users = User.objects.filter(institutional_id__startswith="DEMO-")
        demo_issues = Issue.objects.filter(description__contains="Demo seed reference: DEMO-ISSUE-")
        self.assertEqual(demo_users.count(), 9)
        self.assertEqual(demo_issues.count(), 6)
        self.assertEqual(set(demo_users.values_list("role", flat=True)), {role.value for role in UserRole})
        self.assertEqual(WorkOrder.objects.filter(instructions__contains="Demo seed reference: DEMO-WO-").count(), 4)
        self.assertEqual(RoutingRule.objects.filter(name__startswith="DEMO-RULE-", active=True).count(), 6)
        self.assertTrue(SlaPolicy.objects.get(name="DEMO - Standard campus response").active)

        for issue in demo_issues:
            issue.refresh_from_db()
            assignment = Assignment.objects.get(issue=issue)
            self.assertTrue(assignment.is_automatic)
            self.assertIsNotNone(assignment.team_id)
            self.assertIsNotNone(assignment.user_id)
            self.assertTrue(assignment.user.teams.filter(pk=assignment.team_id).exists())
            self.assertTrue(assignment.user.is_active)
            self.assertIsNotNone(issue.response_due_at)
            self.assertIsNotNone(issue.resolution_due_at)
            self.assertTrue(issue.sla_events.filter(event_type=SlaEvent.Type.STARTED).exists())

        requested = demo_issues.filter(priority_requested_at__isnull=False)
        self.assertEqual(requested.count(), 2)
        for issue in requested:
            self.assertEqual(issue.priority, Issue.Priority.HIGH)
            self.assertEqual(issue.routing_priority, Issue.Priority.MEDIUM)
            self.assertEqual(issue.priority_requested_by.role, UserRole.STAFF)
            self.assertTrue(issue.priority_request_reason)

        demo_student = User.objects.get(institutional_id="DEMO-STU-001")
        demo_student.set_password("Preserved-Demo-Password-2026!")
        demo_student.save(update_fields=["password"])
        before = (User.objects.count(), Issue.objects.count(), Assignment.objects.count(), WorkOrder.objects.count())
        call_command("seed_operational_demo", stdout=StringIO())
        after = (User.objects.count(), Issue.objects.count(), Assignment.objects.count(), WorkOrder.objects.count())
        self.assertEqual(after, before)
        self.assertTrue(User.objects.get(pk=demo_student.pk).check_password("Preserved-Demo-Password-2026!"))

