from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from apps.campus.models import Building, Campus, Location
from apps.users.models import User
from apps.users.roles import UserRole

from .models import Network, NetworkDevice, NetworkMeasurement
from .analytics import get_network_analytics


class NetworkAnalyticsTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.campus = Campus.objects.create(name="Analytics Campus", code="analytics-campus")
        self.other_campus = Campus.objects.create(name="Other Analytics Campus", code="analytics-other")
        self.building = Building.objects.create(campus=self.campus, name="Analytics Engineering", code="analytics-eng")
        self.other_building = Building.objects.create(campus=self.campus, name="Analytics Library", code="analytics-lib")
        self.other_campus_building = Building.objects.create(campus=self.other_campus, name="Other Campus Hall", code="analytics-other-hall")
        self.location = Location.objects.create(building=self.building, name="Floor 2 Lab", code="analytics-floor-2")
        self.other_location = Location.objects.create(building=self.other_building, name="Reading Room", code="analytics-reading")
        self.other_campus_location = Location.objects.create(building=self.other_campus_building, name="Other Campus Office", code="analytics-other-office")
        self.network = Network.objects.create(campus=self.campus, building=self.building, code="analytics-wifi", name="Synthetic Analytics Wi-Fi", kind=Network.Kind.WIFI)
        self.other_network = Network.objects.create(campus=self.campus, building=self.other_building, code="analytics-lan", name="Synthetic Analytics LAN", kind=Network.Kind.LAN)
        self.other_campus_network = Network.objects.create(campus=self.other_campus, code="analytics-wan", name="Synthetic Analytics WAN", kind=Network.Kind.WAN)
        self.device = NetworkDevice.objects.create(device_code="ANALYTICS-AP-1", name="Analytics Access Point", kind=NetworkDevice.Kind.ACCESS_POINT, network=self.network, location=self.location)
        self.other_device = NetworkDevice.objects.create(device_code="ANALYTICS-SW-1", name="Analytics Switch", kind=NetworkDevice.Kind.SWITCH, network=self.other_network, location=self.other_location)
        self.tech = User.objects.create_user("analytics-tech@example.test", "Analytics Tech", "test-password-123", role=UserRole.TECHNICAL_STAFF, technical_specialization="Network")
        self.student = User.objects.create_user("analytics-student@example.test", "Analytics Student", "test-password-123", role=UserRole.STUDENT)
        self.client = APIClient()
        self.measurements = []

    def record(self, *, network=None, location=None, device=None, connection_state="CONNECTED", **metrics):
        record = NetworkMeasurement.objects.create(network=network or self.network, location=location or self.location, device=device, recorded_by=self.tech, connection_state=connection_state, **metrics)
        self.measurements.append(record)
        return record

    def api(self, name, params=None):
        self.client.force_authenticate(self.tech)
        return self.client.get(reverse(name), params or {})

    def test_zero_measurements_returns_honest_empty_summary_and_distributions(self):
        response = self.api("network-analytics-summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_measurements"], 0)
        self.assertEqual(response.data["overall_quality"], "INSUFFICIENT_DATA")
        self.assertIsNone(response.data["latest_measurement"])
        self.assertEqual(response.data["quality_distribution"]["CRITICAL"], {"count": 0, "percentage": 0.0})
        self.assertEqual(response.data["primary_factors"], [])

    def test_summary_counts_real_rows_and_uses_worst_quality_and_factor_denominator(self):
        self.record(latency_ms=10)
        self.record(packet_loss_percent=4)
        self.record(upload_mbps=4)
        self.record(signal_strength_dbm=-80)
        self.record(latency_ms=5, connection_state="DISCONNECTED")
        response = self.api("network-analytics-summary")
        self.assertEqual(response.data["total_measurements"], 5)
        self.assertEqual(response.data["overall_quality"], "CRITICAL")
        self.assertEqual(response.data["quality_distribution"]["EXCELLENT"]["count"], 1)
        self.assertEqual(response.data["quality_distribution"]["FAIR"]["count"], 1)
        self.assertEqual(response.data["quality_distribution"]["POOR"]["count"], 1)
        self.assertEqual(response.data["quality_distribution"]["CRITICAL"]["count"], 2)
        self.assertEqual(sum(row["percentage"] for row in response.data["quality_distribution"].values()), 100.0)
        self.assertEqual(response.data["degraded_measurement_count"], 4)
        self.assertEqual(response.data["primary_factors"][0], {"factor": "CONNECTION_STATUS", "count": 1, "percentage_of_degraded_measurements": 25.0})
        self.assertEqual(response.data["latest_measurement"]["id"], self.measurements[-1].pk)

    def test_all_excellent_window_reports_excellent_not_average(self):
        self.record(latency_ms=5)
        self.record(packet_loss_percent=0)
        summary = self.api("network-analytics-summary").data
        self.assertEqual(summary["overall_quality"], "EXCELLENT")
        self.assertEqual(summary["quality_distribution"]["EXCELLENT"]["count"], 2)
        self.assertEqual(summary["degraded_measurement_count"], 0)

    def test_quality_distribution_largest_remainder_percentages_sum_exactly(self):
        for _ in range(3):
            self.record(latency_ms=1)
        for _ in range(2):
            self.record(latency_ms=45)
        self.record(packet_loss_percent=4)
        self.record(upload_mbps=4)
        distribution = self.api("network-analytics-summary").data["quality_distribution"]
        self.assertEqual(sum(item["percentage"] for item in distribution.values()), 100.0)
        self.assertEqual(distribution["EXCELLENT"]["percentage"], 42.86)
        self.assertEqual(distribution["GOOD"]["percentage"], 28.57)

    def test_all_quality_evaluations_and_insufficient_bucket_are_preserved(self):
        self.record(latency_ms=1)
        self.record(latency_ms=45)
        self.record(packet_loss_percent=4)
        self.record(upload_mbps=4)
        self.record(signal_strength_dbm=-80)
        result = get_network_analytics({"range": "24h"}, now=self.now + timedelta(minutes=1))
        # A valid persisted measurement always has a reading; the shared quality
        # distribution nevertheless has an explicit insufficient-data bucket.
        self.assertEqual(result["summary"]["quality_distribution"]["INSUFFICIENT_DATA"]["count"], 0)
        self.assertEqual(result["summary"]["poor_count"], 1)
        self.assertEqual(result["summary"]["critical_count"], 1)

    def test_aggregator_accounts_for_future_evaluator_insufficient_data_state(self):
        record = self.record(latency_ms=10)
        from .services import evaluate_measurement
        def insufficient(measurement):
            evaluation = evaluate_measurement(measurement)
            evaluation.update(overall_quality="INSUFFICIENT_DATA", primary_factor=None, primary_factor_label=None, reasons=[])
            return evaluation
        with patch("apps.network.analytics.evaluate_measurement", side_effect=insufficient):
            summary = get_network_analytics({"range": "24h"}, now=self.now + timedelta(minutes=1), include=())["summary"]
        self.assertEqual(summary["total_measurements"], 1)
        self.assertEqual(summary["overall_quality"], "INSUFFICIENT_DATA")
        self.assertEqual(summary["insufficient_data_count"], 1)
        self.assertEqual(summary["quality_distribution"]["INSUFFICIENT_DATA"]["count"], 1)
        self.assertIsNone(summary["latest_measurement"]["device_name"])

    def test_one_measurement_latest_summary_contains_related_entities_and_version(self):
        record = self.record(latency_ms=10, device=self.device)
        latest = self.api("network-analytics-summary").data["latest_measurement"]
        self.assertEqual(latest["id"], record.pk)
        self.assertEqual(latest["location_name"], self.location.display_name)
        self.assertEqual(latest["network_name"], self.network.name)
        self.assertEqual(latest["device_name"], self.device.name)
        self.assertEqual(latest["device_type"], NetworkDevice.Kind.ACCESS_POINT)
        self.assertEqual(latest["evaluation_version"], "1.0")

    def test_location_building_device_network_and_campus_groups_use_only_measured_entities(self):
        self.record(latency_ms=50, device=self.device)
        self.record(network=self.other_network, location=self.other_location, device=self.other_device, upload_mbps=4)
        self.record(network=self.other_campus_network, location=self.other_campus_location, latency_ms=1)
        locations = self.api("network-analytics-locations").data["results"]
        buildings = self.api("network-analytics-buildings").data["results"]
        devices = self.api("network-analytics-devices").data["results"]
        networks = self.api("network-analytics-networks").data["results"]
        campuses = self.api("network-analytics-campuses").data["results"]
        self.assertEqual(len(locations), 3)
        self.assertEqual(len(buildings), 3)
        self.assertEqual({row["device_code"] for row in devices}, {"ANALYTICS-AP-1", "ANALYTICS-SW-1"})
        self.assertEqual(len(networks), 3)
        self.assertEqual(len(campuses), 2)
        self.assertEqual(next(row for row in locations if row["id"] == self.location.pk)["measurement_count"], 1)
        self.assertEqual(next(row for row in devices if row["id"] == self.other_device.pk)["overall_quality"], "POOR")
        self.assertEqual({row["id"] for row in buildings}, {self.building.pk, self.other_building.pk, self.other_campus_building.pk})

    def test_problem_lists_are_poor_or_critical_only_and_have_deterministic_priority(self):
        location_b = Location.objects.create(building=self.building, name="Floor 3 Lab", code="analytics-floor-3")
        for _ in range(2):
            self.record(signal_strength_dbm=-80, device=self.device)
        for _ in range(3):
            self.record(location=location_b, network=self.network, upload_mbps=4)
        self.record(network=self.other_network, location=self.other_location, latency_ms=50)
        locations = self.api("network-analytics-problem-locations").data["results"]
        devices = self.api("network-analytics-problem-devices").data["results"]
        self.assertEqual([row["location_name"] for row in locations], ["Floor 2 Lab", "Floor 3 Lab"])
        self.assertEqual([row["critical_count"] for row in locations], [2, 0])
        self.assertEqual([row["device_code"] for row in devices], ["ANALYTICS-AP-1"])

    def test_primary_factor_endpoint_only_counts_degraded_measurements_and_uses_evaluator(self):
        self.record(latency_ms=1)  # Excellent; excluded from the denominator.
        self.record(packet_loss_percent=4)
        self.record(packet_loss_percent=4)
        self.record(signal_strength_dbm=-80)
        self.record(latency_ms=5, connection_state="DISCONNECTED")
        response = self.api("network-analytics-factors")
        factors = {row["factor"]: row for row in response.data["results"]}
        self.assertEqual(factors["PACKET_LOSS"]["count"], 2)
        self.assertEqual(factors["PACKET_LOSS"]["percentage_of_degraded_measurements"], 50.0)
        self.assertEqual(factors["CONNECTION_STATUS"]["count"], 1)
        self.assertEqual(response.data["count"], 3)

    def test_predefined_and_explicit_windows_and_explicit_precedence(self):
        recent = self.record(latency_ms=1)
        old = self.record(network=self.other_network, location=self.other_location, upload_mbps=4)
        NetworkMeasurement.objects.filter(pk=old.pk).update(measured_at=self.now - timedelta(days=8))
        response_24h = self.api("network-analytics-summary", {"range": "24h"})
        response_7d = self.api("network-analytics-summary", {"range": "7d"})
        response_30d = self.api("network-analytics-summary", {"range": "30d"})
        self.assertEqual(response_24h.data["total_measurements"], 1)
        self.assertEqual(response_7d.data["total_measurements"], 1)
        self.assertEqual(response_30d.data["total_measurements"], 2)
        start = (self.now - timedelta(days=9)).isoformat()
        end = (self.now - timedelta(days=7)).isoformat()
        explicit = self.api("network-analytics-summary", {"range": "invalid", "start": start, "end": end})
        self.assertEqual(explicit.data["window"]["range"], "explicit")
        self.assertEqual(explicit.data["total_measurements"], 1)
        self.assertEqual(explicit.data["latest_measurement"]["id"], old.pk)

    def test_invalid_ranges_filters_and_unsupported_source_return_useful_400(self):
        now_text = self.now.isoformat()
        for params in ({"range": "2d"}, {"start": now_text}, {"start": now_text, "end": now_text}, {"start": "2026-01-01T00:00:00", "end": now_text}, {"network": "bad"}, {"quality": "MYSTERY"}, {"source": "browser"}):
            with self.subTest(params=params):
                response = self.api("network-analytics-summary", params)
                self.assertEqual(response.status_code, 400)
                self.assertIn("detail", response.data)

    def test_filters_apply_to_database_and_evaluated_quality_before_grouping(self):
        self.record(latency_ms=1, device=self.device)
        self.record(upload_mbps=4, device=self.device)
        self.record(network=self.other_network, location=self.other_location, device=self.other_device, packet_loss_percent=4)
        response = self.api("network-analytics-summary", {"campus": self.campus.pk, "building": self.building.pk, "location": self.location.pk, "network": self.network.pk, "device": self.device.pk, "device_type": "ACCESS_POINT", "network_type": "WIFI", "connection_state": "CONNECTED", "quality": "POOR"})
        self.assertEqual(response.data["total_measurements"], 1)
        self.assertEqual(response.data["overall_quality"], "POOR")
        self.assertEqual(self.api("network-analytics-summary", {"campus": self.other_campus.pk}).data["total_measurements"], 0)

    def test_pagination_and_fixed_problem_sorting(self):
        loc2 = Location.objects.create(building=self.building, name="Floor 4", code="analytics-floor-4")
        for _ in range(2):
            self.record(signal_strength_dbm=-80)
        for _ in range(2):
            self.record(location=loc2, upload_mbps=4)
        response = self.api("network-analytics-problem-locations", {"page": 1})
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["results"][0]["location_name"], "Floor 2 Lab")
        self.assertIn("window", response.data)

    def test_general_grouped_endpoints_use_page_size_twenty(self):
        for number in range(21):
            location = Location.objects.create(building=self.building, name=f"Page {number:02}", code=f"analytics-page-{number:02}")
            self.record(location=location, latency_ms=10)
        first_page = self.api("network-analytics-locations")
        second_page = self.api("network-analytics-locations", {"page": 2})
        self.assertEqual(first_page.data["count"], 21)
        self.assertEqual(len(first_page.data["results"]), 20)
        self.assertIsNotNone(first_page.data["next"])
        self.assertEqual(len(second_page.data["results"]), 1)
        self.assertIsNone(second_page.data["next"])

    def test_permissions_match_network_measurement_visibility(self):
        self.record(latency_ms=10)
        self.assertEqual(self.client.get(reverse("network-analytics-summary")).status_code, 401)
        self.client.force_authenticate(self.student)
        for name in ("network-analytics-summary", "network-analytics-locations", "network-analytics-factors"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 403)
        self.client.force_authenticate(self.tech)
        self.assertEqual(self.client.get(reverse("network-analytics-summary")).status_code, 200)

    def test_group_order_is_stable_by_name_and_identifier(self):
        self.record(latency_ms=10)
        self.record(network=self.other_network, location=self.other_location, latency_ms=10)
        result = get_network_analytics({"range": "24h"}, now=self.now + timedelta(minutes=1), include=("locations", "networks"))
        self.assertEqual(result["locations"], sorted(result["locations"], key=lambda row: (row["location_name"].casefold(), row["id"])))
        self.assertEqual(result["networks"], sorted(result["networks"], key=lambda row: (row["network_name"].casefold(), row["id"])))

    def test_grouping_uses_one_database_query_without_related_object_n_plus_one(self):
        self.record(latency_ms=10, device=self.device)
        self.record(network=self.other_network, location=self.other_location, device=self.other_device, upload_mbps=4)
        with self.assertNumQueries(1):
            result = get_network_analytics({"range": "24h"}, now=self.now + timedelta(minutes=1), include=("campuses", "locations", "buildings", "devices", "networks"))
            self.assertEqual(len(result["locations"]), 2)
            self.assertEqual(len(result["devices"]), 2)
