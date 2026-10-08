from rest_framework.test import APITestCase

from apps.users.models import User
from apps.users.roles import UserRole

from .models import Notification


class NotificationInboxTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user("student@notifications.test", "Student", "test-password-123", role=UserRole.STUDENT)
        self.other_student = User.objects.create_user("other@notifications.test", "Other student", "test-password-123", role=UserRole.STUDENT)
        self.notification = Notification.objects.create(
            recipient=self.student,
            notification_type="ISSUE_ASSIGNED",
            title="Issue assigned",
            message="A synthetic issue was assigned to an operations team.",
        )
        Notification.objects.create(
            recipient=self.other_student,
            notification_type="ISSUE_ASSIGNED",
            title="Private notification",
            message="This belongs to another account.",
        )

    def test_inbox_is_scoped_to_signed_in_recipient(self):
        self.client.force_authenticate(self.student)

        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.notification.pk)

    def test_recipient_can_mark_own_notification_read(self):
        self.client.force_authenticate(self.student)

        response = self.client.post(f"/api/notifications/{self.notification.pk}/read/", {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.notification.refresh_from_db()
        self.assertIsNotNone(self.notification.read_at)

    def test_recipient_cannot_mark_another_users_notification_read(self):
        self.client.force_authenticate(self.other_student)

        response = self.client.post(f"/api/notifications/{self.notification.pk}/read/", {}, format="json")

        self.assertEqual(response.status_code, 404)
        self.notification.refresh_from_db()
        self.assertIsNone(self.notification.read_at)
