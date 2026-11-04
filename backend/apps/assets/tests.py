from io import BytesIO

from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from apps.campus.models import Campus, Building, Location
from apps.users.models import User
from apps.users.roles import UserRole

from .models import Asset


class AssetApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("reader@example.test", "Asset Reader", "test-password", role=UserRole.STUDENT)
        self.admin = User.objects.create_user("asset-admin@example.test", "Asset Admin", "test-password", role=UserRole.ADMIN)
        campus = Campus.objects.create(name="Development Campus", code="dev-campus")
        building = Building.objects.create(campus=campus, name="Computer Science Building", code="cs")
        location = Location.objects.create(building=building, name="Computer Lab 1", kind=Location.Kind.LABORATORY)
        self.asset = Asset.objects.create(asset_code="AP-CS-001", name="Wi-Fi Access Point", asset_type="Network equipment", location=location)
        self.client.force_authenticate(self.user)

    def test_assets_are_readable_and_qr_endpoint_returns_png(self):
        listing = self.client.get(reverse("asset-list"))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["results"][0]["qr_identifier"], str(self.asset.qr_identifier))
        response = self.client.get(reverse("asset-qr", kwargs={"pk": self.asset.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(Image.open(BytesIO(response.content)).format, "PNG")

    def test_qr_identifiers_are_unique(self):
        second = Asset.objects.create(asset_code="PJ-CS-002", name="Projector", asset_type="Classroom equipment", location=self.asset.location)
        self.assertNotEqual(self.asset.qr_identifier, second.qr_identifier)

    def test_only_campus_admin_can_create_assets_through_the_api(self):
        payload = {"asset_code": "PJ-CS-003", "name": "Classroom Projector", "asset_type": "Classroom equipment", "location": self.asset.location_id}
        rejected = self.client.post(reverse("asset-list"), payload, format="json")
        self.assertEqual(rejected.status_code, 403)
        self.client.force_authenticate(self.admin)
        created = self.client.post(reverse("asset-list"), payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertTrue(created.data["qr_identifier"])
        self.assertEqual(self.client.get(reverse("asset-detail", args=[created.data["id"]])).status_code, 200)
