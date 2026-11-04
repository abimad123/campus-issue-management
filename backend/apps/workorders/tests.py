from datetime import timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.audit.models import AuditEntry
from apps.campus.models import Building, Campus, Location, Team
from apps.issues.models import Issue, IssueCategory
from apps.notifications.models import Notification
from apps.users.models import User
from apps.users.roles import UserRole

from .models import WorkOrder, WorkOrderEvent


class WorkOrderWorkflowTests(TestCase):
    def setUp(self):
        campus = Campus.objects.create(name="Synthetic Test Campus", code="wo-test")
        building = Building.objects.create(campus=campus, name="Test Block", code="test-block")
        location = Location.objects.create(building=building, name="Test Lab")
        self.category = IssueCategory.objects.create(name="Test Maintenance")
        self.team = Team.objects.create(name="Test Facilities")
        self.other_team = Team.objects.create(name="Other Team")
        self.student = User.objects.create_user("student@tests.test", "Student", "password123456", role=UserRole.STUDENT)
        self.staff = User.objects.create_user("staff@tests.test", "Staff", "password123456", role=UserRole.STAFF)
        self.tech = User.objects.create_user("tech@tests.test", "Technician", "password123456", role=UserRole.TECHNICAL_STAFF)
        self.other_tech = User.objects.create_user("other-tech@tests.test", "Other technician", "password123456", role=UserRole.TECHNICAL_STAFF)
        self.supervisor = User.objects.create_user("supervisor@tests.test", "Supervisor", "password123456", role=UserRole.ADMIN)
        self.outside_supervisor = User.objects.create_user("outside@tests.test", "Outside supervisor", "password123456", role=UserRole.ADMIN)
        self.manager = User.objects.create_user("manager@tests.test", "Facilities manager", "password123456", role=UserRole.ADMIN)
        self.admin = User.objects.create_user("admin@tests.test", "Campus admin", "password123456", role=UserRole.ADMIN)
        self.team.members.add(self.tech, self.supervisor)
        self.other_team.members.add(self.other_tech, self.outside_supervisor)
        self.issue = Issue.objects.create(
            title="Repair a damaged lab outlet", description="The outlet cover is loose and the socket needs a safety inspection.",
            category=self.category, location=location, reporter=self.student, assigned_team=self.team,
            priority=Issue.Priority.HIGH, status=Issue.Status.ASSIGNED,
            response_due_at=timezone.now() + timedelta(minutes=20),
            resolution_due_at=timezone.now() + timedelta(hours=2),
        )
        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user)

    def create_work_order(self, *, actor=None):
        self.login(actor or self.supervisor)
        response = self.client.post(f"/api/issues/{self.issue.pk}/work-orders/", {"team": self.team.pk, "instructions": "Inspect the outlet and record the safe condition."}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return WorkOrder.objects.get(pk=response.data["id"])

    def assign(self, work_order, *, actor=None, technician=None, team=None):
        self.login(actor or self.supervisor)
        return self.client.post(f"/api/work-orders/{work_order.pk}/assign/", {
            "team": (team or self.team).pk, "technician": (technician or self.tech).pk,
            "reason": "Assign synthetic test work to the on-team technician",
        }, format="json")

    def test_create_from_issue_preserves_sla_and_records_audit(self):
        response_deadline = self.issue.response_due_at
        resolution_deadline = self.issue.resolution_due_at
        work_order = self.create_work_order()
        self.issue.refresh_from_db()
        self.assertRegex(work_order.number, r"^WO-\d{4}-\d{6}$")
        self.assertEqual(work_order.issue_id, self.issue.pk)
        self.assertEqual(work_order.team_id, self.team.pk)
        self.assertEqual(work_order.priority, self.issue.priority)
        self.assertEqual(self.issue.response_due_at, response_deadline)
        self.assertEqual(self.issue.resolution_due_at, resolution_deadline)
        self.assertEqual(work_order.events.get().event_type, "CREATED")
        self.assertTrue(AuditEntry.objects.filter(action="work_order.created", entity_id=str(work_order.pk)).exists())

    def test_student_and_staff_cannot_create_or_access_work_orders(self):
        self.login(self.student)
        denied = self.client.post(f"/api/issues/{self.issue.pk}/work-orders/", {"team": self.team.pk}, format="json")
        self.assertEqual(denied.status_code, 403)
        work_order = self.create_work_order()
        self.login(self.staff)
        self.assertEqual(self.client.get("/api/work-orders/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/work-orders/{work_order.pk}/").status_code, 404)

    def test_admin_global_scope_and_assignment_validation(self):
        work_order = self.create_work_order()
        wrong_team = self.assign(work_order, team=self.other_team, technician=self.other_tech)
        self.assertEqual(wrong_team.status_code, 200)
        wrong_member = self.assign(work_order, technician=self.other_tech)
        self.assertEqual(wrong_member.status_code, 400)
        wrong_role = self.assign(work_order, technician=self.staff)
        self.assertEqual(wrong_role.status_code, 400)
        self.login(self.outside_supervisor)
        self.assertEqual(self.client.get(f"/api/work-orders/{work_order.pk}/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/work-orders/{work_order.pk}/assign/", {"team": self.team.pk, "technician": self.tech.pk, "reason": "Admin reassigns across teams"}, format="json").status_code, 200)

    def test_technician_accept_start_notes_materials_and_completion(self):
        work_order = self.create_work_order()
        self.assertEqual(self.assign(work_order).status_code, 200)
        self.assertTrue(Notification.objects.filter(recipient=self.tech, notification_type="WORK_ORDER_ASSIGNED", issue=self.issue).exists())
        self.login(self.tech)
        accepted = self.client.post(f"/api/work-orders/{work_order.pk}/accept/", {}, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(accepted.data["status"], WorkOrder.Status.ACCEPTED)
        started = self.client.post(f"/api/work-orders/{work_order.pk}/start/", {}, format="json")
        self.assertEqual(started.status_code, 200, started.data)
        self.assertIsNotNone(started.data["started_at"])
        self.assertEqual(self.client.post(f"/api/work-orders/{work_order.pk}/notes/", {"body": "Inspected the cover and isolated the outlet before repair."}, format="json").status_code, 200)
        material = self.client.post(f"/api/work-orders/{work_order.pk}/materials/", {"name": "Replacement outlet cover", "quantity": "1.00", "note": "Synthetic test material"}, format="json")
        self.assertEqual(material.status_code, 200, material.data)
        empty_resolution = self.client.post(f"/api/work-orders/{work_order.pk}/complete/", {"resolution_summary": "fixed"}, format="json")
        self.assertEqual(empty_resolution.status_code, 400)
        completed = self.client.post(f"/api/work-orders/{work_order.pk}/complete/", {"resolution_summary": "Replaced the damaged cover, tightened the outlet, and confirmed the socket is safe."}, format="json")
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertEqual(completed.data["status"], WorkOrder.Status.COMPLETED)
        self.assertEqual(completed.data["completed_by"], self.tech.pk)
        self.assertTrue(Notification.objects.filter(recipient=self.supervisor, notification_type="WORK_ORDER_AWAITING_VERIFICATION", issue=self.issue).exists())
        event_types = list(WorkOrderEvent.objects.filter(work_order_id=work_order.pk).values_list("event_type", flat=True))
        for event_type in ("ASSIGNED", "ACCEPTED", "STARTED", "NOTE_ADDED", "MATERIAL_RECORDED", "COMPLETED"):
            self.assertIn(event_type, event_types)

    def test_technician_cannot_assign_or_operate_another_technicians_work(self):
        first = self.create_work_order()
        second = self.create_work_order()
        self.assign(first)
        self.login(self.manager)
        self.assertEqual(self.client.post(f"/api/work-orders/{second.pk}/assign/", {"team": self.team.pk, "technician": self.other_tech.pk, "reason": "Invalid team member"}, format="json").status_code, 400)
        self.login(self.tech)
        self.assertEqual(self.client.get(f"/api/work-orders/{second.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/work-orders/{first.pk}/assign/", {"team": self.team.pk, "technician": self.other_tech.pk, "reason": "Not allowed"}, format="json").status_code, 403)
        self.assertEqual(self.client.post(f"/api/work-orders/{first.pk}/verify/", {}, format="json").status_code, 403)

    def test_supervisor_verifies_and_only_then_resolves_in_progress_issue(self):
        work_order = self.create_work_order()
        self.assign(work_order)
        self.login(self.tech)
        self.client.post(f"/api/work-orders/{work_order.pk}/accept/", {}, format="json")
        self.client.post(f"/api/work-orders/{work_order.pk}/start/", {}, format="json")
        completed = self.client.post(f"/api/work-orders/{work_order.pk}/complete/", {"resolution_summary": "Inspected the outlet, replaced the damaged cover, and tested it safely."}, format="json")
        self.assertEqual(completed.status_code, 200, completed.data)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.ASSIGNED)
        self.login(self.staff)
        self.assertEqual(self.client.post(f"/api/work-orders/{work_order.pk}/verify/", {}, format="json").status_code, 404)
        self.login(self.supervisor)
        self.issue.status = Issue.Status.IN_PROGRESS
        self.issue.save(update_fields=["status"])
        verified = self.client.post(f"/api/work-orders/{work_order.pk}/verify/", {}, format="json")
        self.assertEqual(verified.status_code, 200, verified.data)
        self.assertEqual(verified.data["status"], WorkOrder.Status.VERIFIED)
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.RESOLVED)
        self.assertTrue(self.issue.events.filter(to_status=Issue.Status.RESOLVED, note__contains=work_order.number).exists())
        self.assertIsNotNone(WorkOrder.objects.get(pk=work_order.pk).verified_at)
        self.assertTrue(Notification.objects.filter(recipient=self.tech, notification_type="WORK_ORDER_VERIFIED", issue=self.issue).exists())
        closed = self.client.post(f"/api/work-orders/{work_order.pk}/close/", {}, format="json")
        self.assertEqual(closed.status_code, 200, closed.data)
        self.assertEqual(closed.data["status"], WorkOrder.Status.CLOSED)
        self.assertIsNotNone(closed.data["closed_at"])
        self.issue.refresh_from_db()
        self.assertEqual(self.issue.status, Issue.Status.RESOLVED)

    def test_supervisor_can_reject_for_rework_and_technician_resubmits(self):
        work_order = self.create_work_order()
        self.assign(work_order)
        self.login(self.tech)
        self.client.post(f"/api/work-orders/{work_order.pk}/accept/", {}, format="json")
        self.client.post(f"/api/work-orders/{work_order.pk}/start/", {}, format="json")
        self.client.post(f"/api/work-orders/{work_order.pk}/complete/", {"resolution_summary": "Inspected and replaced the outlet cover; safety check passed."}, format="json")
        self.login(self.supervisor)
        rejected = self.client.post(f"/api/work-orders/{work_order.pk}/rework/", {"reason": "Attach a clear photo of the replaced cover."}, format="json")
        self.assertEqual(rejected.status_code, 200, rejected.data)
        self.assertEqual(rejected.data["status"], WorkOrder.Status.REWORK)
        self.assertTrue(Notification.objects.filter(recipient=self.tech, notification_type="WORK_ORDER_REWORK").exists())
        self.login(self.tech)
        self.assertEqual(self.client.post(f"/api/work-orders/{work_order.pk}/start/", {}, format="json").status_code, 200)
        completed = self.client.post(f"/api/work-orders/{work_order.pk}/complete/", {"resolution_summary": "Added the requested photo, rechecked the outlet, and confirmed safe operation."}, format="json")
        self.assertEqual(completed.status_code, 200, completed.data)

    def test_evidence_is_validated_private_and_visible_only_in_work_order_scope(self):
        work_order = self.create_work_order()
        self.assign(work_order)
        self.login(self.tech)
        self.client.post(f"/api/work-orders/{work_order.pk}/accept/", {}, format="json")
        buffer = BytesIO()
        Image.new("RGB", (4, 4), "blue").save(buffer, format="PNG")
        response = self.client.post(f"/api/work-orders/{work_order.pk}/evidence/", {"file": SimpleUploadedFile("proof.png", buffer.getvalue(), content_type="image/png"), "caption": "Synthetic verification photo"}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        file_path = response.data["file_url"].replace("http://testserver", "")
        self.assertEqual(self.client.get(file_path).status_code, 200)
        self.login(self.student)
        self.assertEqual(self.client.get(file_path).status_code, 404)
        self.login(self.staff)
        self.assertEqual(self.client.get(file_path).status_code, 404)

    def test_invalid_transitions_cancellation_and_close_rules(self):
        work_order = self.create_work_order()
        self.assertEqual(self.assign(work_order).status_code, 200)
        self.login(self.tech)
        self.assertEqual(self.client.post(f"/api/work-orders/{work_order.pk}/start/", {}, format="json").status_code, 400)
        self.login(self.manager)
        self.assertEqual(self.client.post(f"/api/work-orders/{work_order.pk}/close/", {}, format="json").status_code, 400)
        cancelled = self.client.post(f"/api/work-orders/{work_order.pk}/cancel/", {"reason": "Duplicate operational task"}, format="json")
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        self.assertEqual(cancelled.data["status"], WorkOrder.Status.CANCELLED)
        self.assertEqual(cancelled.data["cancellation_reason"], "Duplicate operational task")
