from django.urls import reverse
from rest_framework.test import APITestCase
from django.test import SimpleTestCase
from unittest.mock import patch

from apps.assets.models import Asset
from apps.audit.models import AuditEntry
from apps.campus.models import Building, Campus, Location, Team
from apps.issues.models import Issue, IssueCategory
from apps.notifications.models import Notification
from apps.routing.models import Assignment, RoutingRule
from apps.sla.models import SlaEvent, SlaPolicy
from apps.users.models import User
from apps.users.roles import UserRole
from apps.workorders.models import WorkOrder

from .models import IssueNetworkContext, Network, NetworkDevice, NetworkMeasurement
from .services import EVALUATION_VERSION, evaluate_measurement


class NetworkQualityEvaluationTests(SimpleTestCase):
    def evaluate(self, **values):
        class Measurement:
            pk = 42
            network_id = 1
            device_id = None
            location_id = 2
            connection_state = "CONNECTED"
            measured_at = None
            network = type("NetworkRef", (), {"name": "Synthetic Wi-Fi"})()
            location = type("LocationRef", (), {"display_name": "Test Lab"})()
            device = None
        for field in ("latency_ms", "packet_loss_percent", "download_mbps", "upload_mbps", "signal_strength_dbm"):
            setattr(Measurement, field, values.get(field))
        if "connection_state" in values:
            Measurement.connection_state = values["connection_state"]
        Measurement.measured_at = type("Timestamp", (), {"isoformat": lambda self: "2026-01-01T00:00:00+00:00"})()
        return evaluate_measurement(Measurement())

    def test_threshold_boundaries(self):
        cases = [
            ("latency_ms", 30, "EXCELLENT"), ("latency_ms", "30.01", "GOOD"), ("latency_ms", 60, "GOOD"), ("latency_ms", "60.01", "FAIR"), ("latency_ms", 100, "FAIR"), ("latency_ms", "100.01", "POOR"), ("latency_ms", 200, "POOR"), ("latency_ms", "200.01", "CRITICAL"),
            ("packet_loss_percent", 1, "EXCELLENT"), ("packet_loss_percent", "1.01", "GOOD"), ("packet_loss_percent", 3, "GOOD"), ("packet_loss_percent", "3.01", "FAIR"), ("packet_loss_percent", 5, "FAIR"), ("packet_loss_percent", "5.01", "POOR"), ("packet_loss_percent", 10, "POOR"), ("packet_loss_percent", "10.01", "CRITICAL"),
            ("download_mbps", 100, "EXCELLENT"), ("download_mbps", "99.99", "GOOD"), ("download_mbps", 50, "GOOD"), ("download_mbps", "49.99", "FAIR"), ("download_mbps", 20, "FAIR"), ("download_mbps", "19.99", "POOR"), ("download_mbps", 5, "POOR"), ("download_mbps", "4.99", "CRITICAL"),
            ("upload_mbps", 50, "EXCELLENT"), ("upload_mbps", "49.99", "GOOD"), ("upload_mbps", 25, "GOOD"), ("upload_mbps", "24.99", "FAIR"), ("upload_mbps", 10, "FAIR"), ("upload_mbps", "9.99", "POOR"), ("upload_mbps", 2, "POOR"), ("upload_mbps", "1.99", "CRITICAL"),
            ("signal_strength_dbm", -50, "EXCELLENT"), ("signal_strength_dbm", "-50.1", "GOOD"), ("signal_strength_dbm", -60, "GOOD"), ("signal_strength_dbm", "-60.1", "FAIR"), ("signal_strength_dbm", -67, "FAIR"), ("signal_strength_dbm", "-67.1", "POOR"), ("signal_strength_dbm", -75, "POOR"), ("signal_strength_dbm", "-75.1", "CRITICAL"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                result = self.evaluate(**{field: value})
                metric_key = {"latency_ms": "LATENCY", "packet_loss_percent": "PACKET_LOSS", "download_mbps": "DOWNLOAD_THROUGHPUT", "upload_mbps": "UPLOAD_THROUGHPUT", "signal_strength_dbm": "SIGNAL_STRENGTH"}[field]
                metric = next(item for item in result["metrics"] if item["key"] == metric_key)
                self.assertEqual(metric["quality"], expected)

    def test_worst_metric_and_primary_factor_are_deterministic(self):
        result = self.evaluate(latency_ms=10, packet_loss_percent=4, download_mbps=2, signal_strength_dbm=-80)
        self.assertEqual(result["overall_quality"], "CRITICAL")
        self.assertEqual(result["primary_factor"], "SIGNAL_STRENGTH")
        tied = self.evaluate(latency_ms=80, packet_loss_percent=4)
        self.assertEqual(tied["overall_quality"], "FAIR")
        self.assertEqual(tied["primary_factor"], "PACKET_LOSS")

    def test_connection_state_overrides_and_missing_values(self):
        missing = self.evaluate()
        self.assertEqual(missing["overall_quality"], "INSUFFICIENT_DATA")
        self.assertTrue(all(row["value"] is None for row in missing["metrics"] if row["key"] != "CONNECTION_STATUS"))
        self.assertEqual(self.evaluate(connection_state="DISCONNECTED")["overall_quality"], "CRITICAL")
        self.assertEqual(self.evaluate(latency_ms=5, connection_state="DISCONNECTED")["primary_factor"], "CONNECTION_STATUS")
        degraded = self.evaluate(latency_ms=5, connection_state="DEGRADED")
        self.assertEqual(degraded["overall_quality"], "FAIR")
        self.assertEqual(degraded["primary_factor"], "CONNECTION_STATUS")
        self.assertEqual(self.evaluate(latency_ms=300, connection_state="DEGRADED")["overall_quality"], "CRITICAL")
        self.assertEqual(self.evaluate(latency_ms=5, connection_state="UNKNOWN")["overall_quality"], "EXCELLENT")
        self.assertEqual(self.evaluate(connection_state="UNKNOWN")["overall_quality"], "INSUFFICIENT_DATA")

    def test_version_reasoning_and_absence_are_explicit(self):
        result = self.evaluate(latency_ms=31)
        self.assertEqual(result["evaluation_version"], EVALUATION_VERSION)
        self.assertEqual(result["overall_quality"], "GOOD")
        absent = next(row for row in result["metrics"] if row["key"] == "PACKET_LOSS")
        self.assertEqual(absent["status"], "UNAVAILABLE")
        self.assertIsNone(absent["quality"])


class NetworkApiTests(APITestCase):
    def setUp(self):
        self.campus = Campus.objects.create(name="Synthetic Network Campus", code="network-test")
        self.building = Building.objects.create(campus=self.campus, name="Test Computing Block", code="network-test-block")
        self.location = Location.objects.create(building=self.building, name="Test Lab", code="network-test-lab", kind=Location.Kind.LABORATORY)
        self.other_building = Building.objects.create(campus=self.campus, name="Test Library", code="network-test-library")
        self.other_location = Location.objects.create(building=self.other_building, name="Reading Room", code="network-test-reading")
        self.network = Network.objects.create(campus=self.campus, building=self.building, code="test-wifi", name="Test Wi-Fi", kind=Network.Kind.WIFI)
        self.other_network = Network.objects.create(campus=self.campus, building=self.other_building, code="test-lan", name="Test LAN", kind=Network.Kind.LAN)
        self.asset = Asset.objects.create(asset_code="NET-TEST-AP", name="Synthetic Access Point", asset_type="Network equipment", location=self.location)
        self.device = NetworkDevice.objects.create(device_code="NET-TEST-DEVICE", name="Synthetic Lab AP", kind=NetworkDevice.Kind.ACCESS_POINT, network=self.network, location=self.location, asset=self.asset)
        self.student = User.objects.create_user("network-student@example.test", "Network Student", "test-password-123", role=UserRole.STUDENT)
        self.staff = User.objects.create_user("network-staff@example.test", "Network Staff", "test-password-123", role=UserRole.STAFF)
        self.tech = User.objects.create_user("network-tech@example.test", "Network Technician", "test-password-123", role=UserRole.TECHNICIAN)
        self.supervisor = User.objects.create_user("network-supervisor@example.test", "Network Supervisor", "test-password-123", role=UserRole.SUPERVISOR)
        self.it_manager = User.objects.create_user("network-it@example.test", "Network IT Manager", "test-password-123", role=UserRole.IT_MANAGER)
        self.admin = User.objects.create_user("network-admin@example.test", "Network Admin", "test-password-123", role=UserRole.CAMPUS_ADMIN)

    def test_inventory_requires_auth_and_role_scope(self):
        self.assertEqual(self.client.get(reverse("network-device-list")).status_code, 401)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(reverse("network-device-list")).status_code, 403)
        self.client.force_authenticate(self.tech)
        self.assertEqual(self.client.get(reverse("network-device-list")).status_code, 200)
        denied = self.client.post(reverse("network-device-list"), {"device_code": "DENIED", "name": "Denied", "kind": "SWITCH", "network": self.network.pk, "location": self.location.pk}, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_it_manager_can_create_device_and_campus_admin_can_create_network(self):
        self.client.force_authenticate(self.it_manager)
        response = self.client.post(reverse("network-device-list"), {"device_code": "NET-TEST-SW", "name": "Synthetic Test Switch", "kind": "SWITCH", "network": self.network.pk, "location": self.location.pk}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["location_name"], self.location.display_name)
        self.assertTrue(AuditEntry.objects.filter(action="network_device.created", entity_id=str(response.data["id"]), actor=self.it_manager).exists())
        self.client.force_authenticate(self.admin)
        network = self.client.post(reverse("network-list"), {"campus": self.campus.pk, "building": self.building.pk, "code": "test-wan", "name": "Test WAN", "kind": "WAN"}, format="json")
        self.assertEqual(network.status_code, 201, network.data)

    def test_device_rejects_location_outside_network_building(self):
        self.client.force_authenticate(self.it_manager)
        response = self.client.post(reverse("network-device-list"), {"device_code": "BAD-LOCATION", "name": "Invalid device", "kind": "ROUTER", "network": self.network.pk, "location": self.other_location.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("location", response.data)

    def test_network_device_rejects_location_from_another_campus(self):
        other_campus = Campus.objects.create(name="Another Campus", code="network-another")
        other_building = Building.objects.create(campus=other_campus, name="Another Block", code="network-another-block")
        foreign_location = Location.objects.create(building=other_building, name="Foreign Lab")
        self.client.force_authenticate(self.it_manager)
        response = self.client.post(reverse("network-device-list"), {"device_code": "FOREIGN-CAMPUS", "name": "Invalid device", "kind": "GATEWAY", "network": self.network.pk, "location": foreign_location.pk}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_network_rejects_building_from_different_campus(self):
        other_campus = Campus.objects.create(name="Other Synthetic Campus", code="network-other")
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse("network-list"), {"campus": other_campus.pk, "building": self.building.pk, "code": "mismatch", "name": "Mismatched", "kind": "LAN"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_measurement_validates_ranges_and_relationships_and_is_append_only(self):
        self.client.force_authenticate(self.tech)
        url = reverse("network-measurement-list")
        response = self.client.post(url, {"network": self.network.pk, "location": self.location.pk, "device": self.device.pk, "latency_ms": "17.25", "packet_loss_percent": "0.50", "connection_state": "CONNECTED"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["recorded_by"], self.tech.pk)
        self.assertEqual(NetworkMeasurement.objects.get(pk=response.data["id"]).recorded_by, self.tech)
        self.assertEqual(self.client.patch(reverse("network-measurement-detail", args=[response.data["id"]]), {"latency_ms": 4}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(reverse("network-measurement-detail", args=[response.data["id"]])).status_code, 405)

        outside_building = self.client.post(url, {"network": self.network.pk, "location": self.other_location.pk, "download_mbps": 5}, format="json")
        self.assertEqual(outside_building.status_code, 400)
        invalid_device = self.client.post(url, {"network": self.other_network.pk, "location": self.other_location.pk, "device": self.device.pk, "upload_mbps": 5}, format="json")
        self.assertEqual(invalid_device.status_code, 400)
        invalid_value = self.client.post(url, {"network": self.network.pk, "location": self.location.pk, "packet_loss_percent": 101}, format="json")
        self.assertEqual(invalid_value.status_code, 400)
        empty = self.client.post(url, {"network": self.network.pk, "location": self.location.pk}, format="json")
        self.assertEqual(empty.status_code, 400)

    def test_measurement_listing_is_role_restricted_filtered_and_paginated(self):
        NetworkMeasurement.objects.create(network=self.network, location=self.location, recorded_by=self.tech, latency_ms=12, connection_state="CONNECTED")
        NetworkMeasurement.objects.create(network=self.network, location=self.location, recorded_by=self.tech, download_mbps=18, connection_state="DEGRADED")
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(reverse("network-measurement-list")).status_code, 403)
        self.client.force_authenticate(self.tech)
        response = self.client.get(reverse("network-measurement-list"), {"network": self.network.pk, "connection_state": "CONNECTED", "ordering": "latency_ms"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["latency_ms"], "12.00")
        self.assertIn("quality_evaluation", response.data["results"][0])

    def test_evaluation_endpoint_is_role_restricted_and_returns_explanation(self):
        measurement = NetworkMeasurement.objects.create(network=self.network, location=self.location, recorded_by=self.tech, latency_ms=42, packet_loss_percent=4, connection_state="CONNECTED")
        url = reverse("network-measurement-evaluation", args=[measurement.pk])
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(self.tech)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["overall_quality"], "FAIR")
        self.assertEqual(response.data["primary_factor"], "PACKET_LOSS")
        self.assertEqual(response.data["evaluation_version"], EVALUATION_VERSION)
        self.assertEqual(self.client.get(reverse("network-measurement-evaluation", args=[999999])).status_code, 404)

    def make_measurement(self, **values):
        return NetworkMeasurement.objects.create(
            network=self.network,
            location=self.location,
            recorded_by=self.tech,
            latency_ms=values.pop("latency_ms", 250),
            connection_state=values.pop("connection_state", "CONNECTED"),
            **values,
        )

    def issue_payload(self, category, **values):
        return {
            "title": "Computer lab Wi-Fi drops",
            "description": "Wireless access drops repeatedly in the computer lab during classes.",
            "category": category.pk,
            "location": self.location.pk,
            "priority": "HIGH",
            **values,
        }

    def test_it_manager_creates_issue_from_measurement_through_normal_pipeline(self):
        category = IssueCategory.objects.create(name="Wi-Fi")
        team = Team.objects.create(name="Synthetic Network Response")
        team.members.add(self.supervisor)
        rule = RoutingRule.objects.create(name="Network context route", category=category, target_team=team)
        policy = SlaPolicy.objects.create(name="Network context SLA", category=category, response_time_seconds=300, resolution_time_seconds=1800)
        measurement = self.make_measurement(latency_ms=240, packet_loss_percent="12.00")
        self.client.force_authenticate(self.it_manager)

        response = self.client.post(
            reverse("network-measurement-create-issue", args=[measurement.pk]),
            self.issue_payload(category),
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        issue = Issue.objects.get(pk=response.data["id"])
        context = IssueNetworkContext.objects.get(issue=issue)
        self.assertEqual(issue.reporter, self.it_manager)
        self.assertEqual(issue.assigned_team, team)
        self.assertEqual(issue.status, Issue.Status.ASSIGNED)
        self.assertEqual(issue.sla_policy, policy)
        self.assertIsNotNone(issue.response_due_at)
        self.assertEqual(issue.sla_events.get().event_type, SlaEvent.Type.STARTED)
        self.assertEqual(issue.assignments.get().routing_rule, rule)
        self.assertTrue(issue.assignments.get().is_automatic)
        self.assertTrue(Notification.objects.filter(issue=issue, recipient=self.supervisor, notification_type="ISSUE_ASSIGNED").exists())
        self.assertEqual(context.network_measurement, measurement)
        self.assertEqual(context.created_by, self.it_manager)
        self.assertEqual(context.evaluator_version, EVALUATION_VERSION)
        self.assertEqual(context.overall_quality, "CRITICAL")
        self.assertEqual(context.primary_factor, "PACKET_LOSS")
        self.assertEqual(WorkOrder.objects.filter(issue=issue).count(), 0)

    def test_attach_existing_issue_snapshots_provenance_and_rejects_duplicates(self):
        category = IssueCategory.objects.create(name="Network")
        issue = Issue.objects.create(
            title="Existing network complaint",
            description="Students cannot maintain a stable network connection in this location.",
            category=category,
            location=self.location,
            reporter=self.student,
            status=Issue.Status.IN_PROGRESS,
        )
        measurement = self.make_measurement()
        self.client.force_authenticate(self.it_manager)
        evaluation = {"evaluation_version": "test-snapshot-2", "overall_quality": "POOR", "primary_factor": "LATENCY"}

        with patch("apps.network.services.evaluate_measurement", return_value=evaluation):
            response = self.client.post(
                reverse("issue-network-context", args=[issue.pk]),
                {"network_measurement": measurement.pk},
                format="json",
            )

        self.assertEqual(response.status_code, 201, response.data)
        context = IssueNetworkContext.objects.get(issue=issue)
        self.assertEqual(context.created_by, self.it_manager)
        self.assertIsNotNone(context.created_at)
        self.assertEqual(context.evaluator_version, "test-snapshot-2")
        self.assertEqual(context.overall_quality, "POOR")
        self.assertEqual(context.primary_factor, "LATENCY")
        issue.refresh_from_db()
        self.assertEqual(issue.status, Issue.Status.IN_PROGRESS)
        self.assertIsNone(issue.assigned_team_id)
        self.assertEqual(Assignment.objects.filter(issue=issue).count(), 0)
        self.assertEqual(WorkOrder.objects.filter(issue=issue).count(), 0)
        self.assertEqual(Notification.objects.filter(issue=issue).count(), 0)
        self.assertTrue(AuditEntry.objects.filter(action="issue.network_context_attached", actor=self.it_manager, entity_id=str(issue.pk)).exists())

        duplicate = self.client.post(
            reverse("issue-network-context", args=[issue.pk]),
            {"network_measurement": measurement.pk},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("already attached", str(duplicate.data).lower())
        context_response = self.client.get(reverse("issue-network-context", args=[issue.pk]))
        self.assertEqual(context_response.status_code, 200)
        self.assertEqual(context_response.data["count"], 1)
        self.assertEqual(context_response.data["results"][0]["measurement_id"], measurement.pk)

    def test_technician_can_create_contextual_issue_but_cannot_resolve_it_directly(self):
        category = IssueCategory.objects.create(name="Network")
        measurement = self.make_measurement()
        self.client.force_authenticate(self.tech)
        response = self.client.post(
            reverse("network-measurement-create-issue", args=[measurement.pk]),
            self.issue_payload(category),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        issue = Issue.objects.get(pk=response.data["id"])
        self.assertEqual(issue.reporter, self.tech)
        self.assertTrue(IssueNetworkContext.objects.filter(issue=issue, network_measurement=measurement).exists())
        issue.assigned_to = self.tech
        issue.status = Issue.Status.IN_PROGRESS
        issue.save(update_fields=["assigned_to", "status", "updated_at"])
        denied = self.client.post(reverse("issue-status", args=[issue.pk]), {"status": Issue.Status.RESOLVED}, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_context_actions_reject_roles_without_network_access(self):
        category = IssueCategory.objects.create(name="Network")
        issue = Issue.objects.create(
            title="Student network report",
            description="Network access is not available in the room during the evening.",
            category=category,
            location=self.location,
            reporter=self.student,
        )
        measurement = self.make_measurement()
        facility_manager = User.objects.create_user("facility@example.test", "Facility Manager", "test-password-123", role=UserRole.FACILITY_MANAGER)
        department_head = User.objects.create_user("head@example.test", "Department Head", "test-password-123", role=UserRole.DEPARTMENT_HEAD)
        for user in (self.student, self.staff, facility_manager, department_head):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                self.assertEqual(self.client.get(reverse("network-measurement-evaluation", args=[measurement.pk])).status_code, 403)
                self.assertEqual(self.client.post(reverse("network-measurement-create-issue", args=[measurement.pk]), self.issue_payload(category), format="json").status_code, 403)
                self.assertEqual(self.client.post(reverse("issue-network-context", args=[issue.pk]), {"network_measurement": measurement.pk}, format="json").status_code, 403)
                self.assertEqual(self.client.get(reverse("issue-network-context", args=[issue.pk])).status_code, 403)

    def test_supervisor_scope_and_technician_object_permission_are_preserved(self):
        category = IssueCategory.objects.create(name="Network")
        measurement = self.make_measurement()
        own_team = Team.objects.create(name="Supervisor's network team")
        foreign_team = Team.objects.create(name="Another network team")
        own_team.members.add(self.supervisor)
        own_issue = Issue.objects.create(
            title="Issue in supervisor scope",
            description="Network access needs a review by the assigned operational team.",
            category=category,
            location=self.location,
            reporter=self.student,
            assigned_team=own_team,
            status=Issue.Status.ASSIGNED,
        )
        foreign_issue = Issue.objects.create(
            title="Issue outside supervisor scope",
            description="Network access needs a review by a different operational team.",
            category=category,
            location=self.location,
            reporter=self.student,
            assigned_team=foreign_team,
            status=Issue.Status.ASSIGNED,
        )
        self.client.force_authenticate(self.supervisor)
        accepted = self.client.post(reverse("issue-network-context", args=[own_issue.pk]), {"network_measurement": measurement.pk}, format="json")
        self.assertEqual(accepted.status_code, 201, accepted.data)
        self.assertEqual(self.client.post(reverse("issue-network-context", args=[foreign_issue.pk]), {"network_measurement": measurement.pk}, format="json").status_code, 404)

        assigned_issue = Issue.objects.create(
            title="Technician issue",
            description="A technician can see this assigned issue but cannot attach administrative context.",
            category=category,
            location=self.location,
            reporter=self.student,
            assigned_to=self.tech,
        )
        self.client.force_authenticate(self.tech)
        denied = self.client.post(reverse("issue-network-context", args=[assigned_issue.pk]), {"network_measurement": measurement.pk}, format="json")
        self.assertEqual(denied.status_code, 403)

    def test_context_creation_rolls_back_issue_and_normal_pipeline_on_failure(self):
        category = IssueCategory.objects.create(name="Network")
        measurement = self.make_measurement()
        self.client.force_authenticate(self.it_manager)
        initial_issue_count = Issue.objects.count()
        with patch("apps.network.services.IssueNetworkContext.objects.create", side_effect=RuntimeError("simulated context failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("network-measurement-create-issue", args=[measurement.pk]),
                    self.issue_payload(category),
                    format="json",
                )
        self.assertEqual(Issue.objects.count(), initial_issue_count)
        self.assertEqual(IssueNetworkContext.objects.count(), 0)
        self.assertEqual(Assignment.objects.count(), 0)
        self.assertEqual(SlaEvent.objects.count(), 0)
