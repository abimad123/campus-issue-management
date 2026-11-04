from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from .models import User
from .roles import UserRole


class AuthenticationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "student@example.test", "Sample Student", "A-development-password-42", role=UserRole.STUDENT,
            institutional_id="STU-TEST-001",
        )

    def test_login_me_and_logout_use_session_authentication(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        unauthenticated = csrf_client.get(reverse("current-user"))
        self.assertEqual(unauthenticated.status_code, 401)

        csrf_response = csrf_client.get(reverse("csrf-cookie"))
        self.assertEqual(csrf_response.status_code, 200)
        csrf_token = csrf_client.cookies["csrftoken"].value

        login_response = csrf_client.post(
            reverse("login"),
            {"identifier": self.user.institutional_id, "password": "A-development-password-42"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.data["email"], self.user.email)
        self.assertIn("sessionid", login_response.cookies)

        csrf_token = csrf_client.cookies["csrftoken"].value
        me_response = csrf_client.get(reverse("current-user"))
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["role"], UserRole.STUDENT)

        logout_response = csrf_client.post(reverse("logout"), {}, format="json", HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(csrf_client.get(reverse("current-user")).status_code, 401)

    def test_login_rejects_bad_credentials_and_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get(reverse("csrf-cookie")).cookies["csrftoken"].value
        rejected = client.post(
            reverse("login"), {"identifier": self.user.email, "password": "wrong"}, format="json", HTTP_X_CSRFTOKEN=csrf
        )
        self.assertEqual(rejected.status_code, 400)
        blocked = APIClient(enforce_csrf_checks=True).post(
            reverse("login"), {"identifier": self.user.email, "password": "A-development-password-42"}, format="json"
        )
        self.assertEqual(blocked.status_code, 403)

    def test_inactive_users_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = self.client.post(
            reverse("login"), {"identifier": self.user.email, "password": "A-development-password-42"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_all_four_roles_authenticate_and_role_comes_from_database(self):
        from .models import User

        users = [self.user]
        for role in (UserRole.STAFF, UserRole.TECHNICAL_STAFF, UserRole.ADMIN):
            users.append(User.objects.create_user(
                f"{role.lower()}@example.test", role.label, "A-development-password-42", role=role,
                institutional_id=f"TEST-{role}",
            ))
        for user in users:
            with self.subTest(role=user.role):
                response = self.client.post(reverse("login"), {
                    "identifier": user.institutional_id, "password": "A-development-password-42",
                    # A client-supplied role must never override the database account.
                    "role": UserRole.ADMIN,
                }, format="json")
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["role"], user.role)

    def test_admin_summary_is_backend_restricted(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/auth/admin/summary/").status_code, 403)
        admin = User.objects.create_user("summary-admin@example.test", "Summary Admin", "test-password", role=UserRole.ADMIN)
        technical_staff = User.objects.create_user("summary-tech@example.test", "Summary Technician", "test-password", role=UserRole.TECHNICAL_STAFF)
        self.client.force_authenticate(technical_staff)
        self.assertEqual(self.client.get("/api/auth/admin/summary/").status_code, 403)
        self.client.force_authenticate(admin)
        response = self.client.get("/api/auth/admin/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data["user_counts"]), {"STUDENT", "STAFF", "TECHNICAL_STAFF", "ADMIN"})
