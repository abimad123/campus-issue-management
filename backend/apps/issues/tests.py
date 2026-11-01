from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APITransactionTestCase, APITestCase
from rest_framework.exceptions import ValidationError

from apps.assets.models import Asset
from apps.campus.models import Building, Campus, Location, Team
from apps.users.models import User
from apps.users.roles import UserRole

from .models import Issue, IssueCategory, IssueEvent


def png_upload(name="issue.png"):
    image = Image.new("RGB", (16, 16), color=(180, 30, 40))
    content = BytesIO()
    image.save(content, format="PNG")
    return SimpleUploadedFile(name, content.getvalue(), content_type="image/png")


class IssueApiTestSetup:
    def setUp(self):
        self.student = User.objects.create_user("student@example.test", "Sample Student", "test-password", role=UserRole.STUDENT)
        self.other_student = User.objects.create_user("other@example.test", "Other Student", "test-password", role=UserRole.STUDENT)
        self.admin = User.objects.create_user("admin@example.test", "Campus Admin", "test-password", role=UserRole.CAMPUS_ADMIN)
        self.technician = User.objects.create_user("tech@example.test", "Sample Technician", "test-password", role=UserRole.TECHNICIAN)
        campus = Campus.objects.create(name="Development Campus", code="development")
        building = Building.objects.create(campus=campus, name="Academic Block", code="academic")
        self.location = Location.objects.create(building=building, name="Classroom 1", kind=Location.Kind.CLASSROOM)
        self.category = IssueCategory.objects.create(name="Electrical")
        self.asset = Asset.objects.create(asset_code="EP-AC-001", name="Electrical Panel", asset_type="Electrical equipment", location=self.location)
        self.client.force_authenticate(self.student)

    def payload(self, **updates):
        data = {
            "title": "Classroom lights are out",
            "description": "The lights in the room are not working since this morning.",
            "category": self.category.pk,
            "location": self.location.pk,
            "priority": Issue.Priority.MEDIUM,
        }
        data.update(updates)
        return data

class IssueApiTests(IssueApiTestSetup, APITestCase):
    def test_student_can_create_and_view_only_their_own_issue(self):
        response = self.client.post(reverse("issue-list"), self.payload(), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        issue = Issue.objects.get(pk=response.data["id"])
        self.assertEqual(issue.reporter, self.student)
        self.assertRegex(issue.ticket_number, r"^ISS-\d{4}-\d{6}$")
        self.assertEqual(response.data["status"], Issue.Status.OPEN)
        self.assertEqual(IssueEvent.objects.filter(issue=issue).count(), 1)

        own_detail = self.client.get(reverse("issue-detail", args=[issue.pk]))
        self.assertEqual(own_detail.status_code, 200)
        self.client.force_authenticate(self.other_student)
        other_detail = self.client.get(reverse("issue-detail", args=[issue.pk]))
        self.assertEqual(other_detail.status_code, 404)
        self.assertEqual(self.client.get(reverse("issue-list")).data["count"], 0)
        self.assertEqual(self.client.patch(reverse("issue-detail", args=[issue.pk]), {"title": "Changed"}, format="json").status_code, 403)

    def test_supervisor_can_review_unassigned_issue_but_cannot_transition_before_assignment(self):
        team = Team.objects.create(name="Supervisor test team")
        supervisor = User.objects.create_user("supervisor@example.test", "Supervisor", "test-password", role=UserRole.SUPERVISOR)
        team.members.add(supervisor)
        created = self.client.post(reverse("issue-list"), self.payload(), format="json")
        issue_id = created.data["id"]

        self.client.force_authenticate(supervisor)
        self.assertEqual(self.client.get(reverse("issue-detail", args=[issue_id])).status_code, 200)
        transition = self.client.post(reverse("issue-status", args=[issue_id]), {"status": Issue.Status.IN_REVIEW}, format="json")
        self.assertEqual(transition.status_code, 403)
        assignment = self.client.post(f"/api/issues/{issue_id}/assign/", {"team": team.pk, "reason": "Supervisor accepts unassigned issue"}, format="json")
        self.assertEqual(assignment.status_code, 201, assignment.data)
        issue = Issue.objects.get(pk=issue_id)
        self.assertEqual(issue.assigned_team_id, team.pk)
        self.assertEqual(issue.status, Issue.Status.ASSIGNED)

    def test_create_validation_and_category_location_asset_apis(self):
        invalid = self.client.post(reverse("issue-list"), {**self.payload(), "description": "short"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        with_asset = self.client.post(reverse("issue-list"), self.payload(asset=self.asset.pk), format="json")
        self.assertEqual(with_asset.status_code, 201, with_asset.data)
        self.assertEqual(with_asset.data["asset"], self.asset.pk)

        categories = self.client.get(reverse("issue-category-list"))
        self.assertEqual(categories.status_code, 200)
        self.assertEqual(categories.data["results"][0]["name"], "Electrical")
        self.assertEqual(self.client.get(reverse("location-list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("asset-list")).status_code, 200)
        forbidden = self.client.post(reverse("issue-category-list"), {"name": "New category"}, format="json")
        self.assertEqual(forbidden.status_code, 403)

    def test_filters_and_pagination(self):
        for number in range(23):
            Issue.objects.create(
                title=f"Issue report {number:02d}",
                description="A sufficiently descriptive issue report for pagination coverage.",
                category=self.category,
                location=self.location,
                reporter=self.student,
                priority=Issue.Priority.HIGH if number % 2 else Issue.Priority.LOW,
            )
        first_page = self.client.get(reverse("issue-list"))
        self.assertEqual(first_page.data["count"], 23)
        self.assertEqual(len(first_page.data["results"]), 20)
        filtered = self.client.get(reverse("issue-list"), {"priority": Issue.Priority.HIGH, "category": self.category.pk})
        self.assertEqual(filtered.data["count"], 11)

    def test_assigned_technician_can_see_and_progress_only_assigned_issues(self):
        issue = Issue.objects.create(
            title="Network access point is offline",
            description="The access point in the computer lab is offline and needs inspection.",
            category=self.category,
            location=self.location,
            reporter=self.student,
            assigned_to=self.technician,
            status=Issue.Status.ASSIGNED,
        )
        self.client.force_authenticate(self.technician)
        self.assertEqual(self.client.get(reverse("issue-list")).data["count"], 1)
        changed = self.client.post(reverse("issue-status", args=[issue.pk]), {"status": Issue.Status.IN_PROGRESS}, format="json")
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(issue.events.count(), 1)
        for terminal_status in (Issue.Status.RESOLVED, Issue.Status.CLOSED, Issue.Status.REOPENED):
            denied = self.client.post(reverse("issue-status", args=[issue.pk]), {"status": terminal_status}, format="json")
            self.assertEqual(denied.status_code, 403, denied.data)
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.IN_PROGRESS)
        self.assertIsNone(issue.resolved_at)
        self.assertEqual(issue.events.count(), 1)

    def test_manager_and_supervisor_can_resolve_issue_without_work_order(self):
        team = Team.objects.create(name="Verification team")
        supervisor = User.objects.create_user("reviewer@example.test", "Supervisor", "test-password", role=UserRole.SUPERVISOR)
        team.members.add(supervisor)

        for actor, suffix in ((self.admin, "admin"), (supervisor, "supervisor")):
            issue = Issue.objects.create(
                title=f"Repair completed by {suffix}",
                description="A campus repair is ready to be reviewed and resolved without a field work order.",
                category=self.category,
                location=self.location,
                reporter=self.student,
                assigned_team=team,
                status=Issue.Status.IN_PROGRESS,
            )
            self.client.force_authenticate(actor)
            response = self.client.post(reverse("issue-status", args=[issue.pk]), {"status": Issue.Status.RESOLVED}, format="json")
            self.assertEqual(response.status_code, 200, response.data)
            issue.refresh_from_db()
            self.assertEqual(issue.status, Issue.Status.RESOLVED)
            self.assertIsNotNone(issue.resolved_at)
            self.assertEqual(issue.events.get().to_status, Issue.Status.RESOLVED)

    def test_student_cannot_change_status(self):
        issue = Issue.objects.create(
            title="Broken classroom fixture",
            description="A ceiling fixture has stopped working in the classroom.",
            category=self.category,
            location=self.location,
            reporter=self.student,
        )
        response = self.client.post(reverse("issue-status", args=[issue.pk]), {"status": Issue.Status.IN_REVIEW}, format="json")
        self.assertEqual(response.status_code, 403)


class IssueAttachmentApiTests(IssueApiTestSetup, APITransactionTestCase):
    def test_photo_upload_accepts_images_and_rejects_non_images(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parents[2]) as media_dir, override_settings(MEDIA_ROOT=media_dir):
            valid = self.client.post(reverse("issue-list"), {**self.payload(), "photo": png_upload()}, format="multipart")
            self.assertEqual(valid.status_code, 201, valid.data)
            issue = Issue.objects.get(pk=valid.data["id"])
            attachment = issue.attachments.get()
            self.assertEqual(attachment.content_type, "image/png")
            file_response = self.client.get(reverse("issue-attachment-file", args=[attachment.pk]))
            self.assertEqual(file_response.status_code, 200)
            self.assertEqual(file_response["X-Content-Type-Options"], "nosniff")
            file_response.close()
            self.client.force_authenticate(self.other_student)
            self.assertEqual(self.client.get(reverse("issue-attachment-file", args=[attachment.pk])).status_code, 404)
            self.client.force_authenticate(self.student)

            bad_file = SimpleUploadedFile("script.exe", b"not an image", content_type="application/octet-stream")
            invalid = self.client.post(reverse("issue-list"), {**self.payload(), "photo": bad_file}, format="multipart")
            self.assertEqual(invalid.status_code, 400)


class IssueTransitionConcurrencyTests(IssueApiTestSetup, APITransactionTestCase):
    def test_concurrent_status_transitions_validate_against_locked_current_state(self):
        if connection.vendor != "postgresql":
            self.skipTest("Row-lock concurrency behavior is verified on PostgreSQL only.")
        from apps.issues.services import transition_issue

        issue = Issue.objects.create(
            title="Concurrent transition verification",
            description="Two operators attempt the same issue transition at the same time.",
            category=self.category,
            location=self.location,
            reporter=self.student,
            assigned_to=self.technician,
            status=Issue.Status.ASSIGNED,
        )
        barrier = Barrier(2)

        def attempt_transition():
            close_old_connections()
            try:
                stale_issue = Issue.objects.get(pk=issue.pk)
                barrier.wait(timeout=10)
                try:
                    transition_issue(stale_issue, new_status=Issue.Status.IN_PROGRESS, actor=self.technician)
                    return "updated"
                except ValidationError:
                    return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: attempt_transition(), range(2)))

        self.assertCountEqual(outcomes, ["updated", "rejected"])
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.IN_PROGRESS)
        self.assertEqual(issue.events.filter(to_status=Issue.Status.IN_PROGRESS).count(), 1)
