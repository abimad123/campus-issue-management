from django.urls import reverse
from rest_framework.test import APITestCase

from apps.users.models import User
from apps.users.roles import UserRole

from .models import Building, Campus, Location


class CampusApiTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user("campus-reader@example.test", "Campus Reader", "test-password", role=UserRole.STUDENT)
        self.campus = Campus.objects.create(name="Development Campus", code="dev-campus")
        self.building = Building.objects.create(campus=self.campus, name="Academic Block", code="academic")
        self.location = Location.objects.create(building=self.building, name="Classroom 1", kind=Location.Kind.CLASSROOM)
        self.client.force_authenticate(self.student)

    def test_authenticated_users_can_load_campus_hierarchy(self):
        self.assertEqual(self.client.get(reverse("campus-list")).data["results"][0]["name"], self.campus.name)
        self.assertEqual(self.client.get(reverse("building-list")).data["results"][0]["campus_name"], self.campus.name)
        locations = self.client.get(reverse("location-list"))
        self.assertEqual(locations.data["results"][0]["display_name"], "Academic Block · Classroom 1")

    def test_non_admin_cannot_modify_campus_structure(self):
        response = self.client.post(reverse("location-list"), {"name": "New room", "kind": "CLASSROOM"})
        self.assertEqual(response.status_code, 403)
