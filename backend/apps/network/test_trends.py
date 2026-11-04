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
from .trends import get_network_trends


class NetworkTrendTests(TestCase):
    def setUp(self):
        self.now = timezone.now().replace(minute=0, second=0, microsecond=0)
        self.start = self.now - timedelta(days=30)
        self.end = self.now + timedelta(hours=1)
        self.campus = Campus.objects.create(name="Trend Synthetic Campus", code="trend-campus")
        self.other_campus = Campus.objects.create(name="Other Trend Campus", code="trend-campus-2")
        self.building = Building.objects.create(campus=self.campus, name="Trend Engineering", code="trend-eng")
        self.other_building = Building.objects.create(campus=self.campus, name="Trend Library", code="trend-lib")
        self.other_campus_building = Building.objects.create(campus=self.other_campus, name="Other Trend Building", code="trend-other")
        self.location = Location.objects.create(building=self.building, name="Trend Lab", code="trend-lab")
        self.other_location = Location.objects.create(building=self.other_building, name="Trend Reading Room", code="trend-reading")
        self.other_campus_location = Location.objects.create(building=self.other_campus_building, name="Other Location", code="trend-other-loc")
        self.network = Network.objects.create(campus=self.campus, building=self.building, code="trend-wifi", name="Trend Wi-Fi", kind=Network.Kind.WIFI)
        self.other_network = Network.objects.create(campus=self.campus, building=self.other_building, code="trend-lan", name="Trend LAN", kind=Network.Kind.LAN)
        self.other_campus_network = Network.objects.create(campus=self.other_campus, code="trend-wan", name="Other WAN", kind=Network.Kind.WAN)
        self.device = NetworkDevice.objects.create(device_code="TREND-AP-1", name="Trend Access Point", kind=NetworkDevice.Kind.ACCESS_POINT, network=self.network, location=self.location)
        self.other_device = NetworkDevice.objects.create(device_code="TREND-AP-2", name="Other Access Point", kind=NetworkDevice.Kind.ACCESS_POINT, network=self.other_network, location=self.other_location)
        self.reader = User.objects.create_user("trend-reader@example.test", "Trend Reader", "test-password-123", role=UserRole.TECHNICAL_STAFF, technical_specialization="Network")
        self.student = User.objects.create_user("trend-student@example.test", "Trend Student", "test-password-123", role=UserRole.STUDENT)
        self.client = APIClient()

    def record(self, when, *, network=None, location=None, device=None, connection_state="CONNECTED", **metrics):
        measurement = NetworkMeasurement.objects.create(
            network=network or self.network,
            location=location or self.location,
            device=device,
            recorded_by=self.reader,
            connection_state=connection_state,
            **metrics,
        )
        NetworkMeasurement.objects.filter(pk=measurement.pk).update(measured_at=when)
        measurement.refresh_from_db()
        return measurement

    def explicit(self, start=None, end=None, **filters):
        return get_network_trends({"start": (start or self.start).isoformat(), "end": (end or self.end).isoformat(), **filters})

    def test_empty_window_returns_no_buckets_and_no_data_comparison(self):
        result = get_network_trends({"range": "24h"}, now=self.now)
        self.assertEqual(result["buckets"], [])
        self.assertEqual(result["bucket_size"], "hour")
        self.assertEqual(result["comparison"]["status"], "NO_DATA")

    def test_one_measurement_has_distribution_percentages_latest_and_no_comparison(self):
        measured_at = self.now - timedelta(hours=2)
        self.record(measured_at, latency_ms=10)
        result = get_network_trends({"range": "24h"}, now=self.now)
        bucket = result["buckets"][0]
        self.assertEqual(result["comparison"]["status"], "NO_COMPARISON")
        self.assertEqual(bucket["total_measurements"], 1)
        self.assertEqual(bucket["excellent"], 1)
        self.assertEqual(bucket["excellent_percentage"], 100.0)
        self.assertEqual(bucket["degraded"], 0)
        self.assertEqual(bucket["overall_quality"], "EXCELLENT")
        self.assertEqual(bucket["latest_measurement_at"], measured_at.isoformat())

    def test_24_hour_range_uses_hourly_buckets_and_start_inclusive_end_exclusive(self):
        start = self.now - timedelta(hours=24)
        self.record(start, latency_ms=20)
        self.record(self.now - timedelta(hours=1), latency_ms=20)
        self.record(self.now, latency_ms=20)
        result = get_network_trends({"start": start.isoformat(), "end": self.now.isoformat()})
        self.assertEqual(result["bucket_size"], "hour")
        self.assertEqual(len(result["buckets"]), 2)
        self.assertEqual(sum(bucket["total_measurements"] for bucket in result["buckets"]), 2)

    def test_7d_and_30d_ranges_use_daily_buckets(self):
        self.record(self.now - timedelta(days=6), latency_ms=10)
        self.record(self.now - timedelta(days=2), latency_ms=10)
        seven = get_network_trends({"range": "7d"}, now=self.now)
        thirty = get_network_trends({"range": "30d"}, now=self.now)
        self.assertEqual(seven["bucket_size"], "day")
        self.assertEqual(thirty["bucket_size"], "day")
        self.assertEqual(len(seven["buckets"]), 2)
        self.assertEqual(len(thirty["buckets"]), 2)

    def test_explicit_long_range_uses_daily_buckets_and_range_takes_precedence(self):
        self.record(self.now - timedelta(days=2), latency_ms=10)
        result = get_network_trends({"range": "not-a-range", "start": self.start.isoformat(), "end": self.end.isoformat()})
        self.assertEqual(result["window"]["range"], "explicit")
        self.assertEqual(result["bucket_size"], "day")

    def test_quality_counts_degraded_and_poor_critical_use_evaluator_output(self):
        when = self.now - timedelta(days=1)
        self.record(when, latency_ms=10)
        self.record(when + timedelta(minutes=1), packet_loss_percent=4)
        self.record(when + timedelta(minutes=2), upload_mbps=4)
        self.record(when + timedelta(minutes=3), signal_strength_dbm=-80)
        self.record(when + timedelta(minutes=4), latency_ms=5, connection_state="DISCONNECTED")
        bucket = self.explicit()["buckets"][0]
        self.assertEqual(bucket["total_measurements"], 5)
        self.assertEqual((bucket["excellent"], bucket["fair"], bucket["poor"], bucket["critical"]), (1, 1, 1, 2))
        self.assertEqual(bucket["degraded"], 4)
        self.assertEqual(bucket["poor_or_critical"], 3)
        self.assertEqual(bucket["degraded_percentage"], 80.0)
        self.assertEqual(bucket["overall_quality"], "CRITICAL")
        self.assertEqual(sum(bucket[f"{quality}_percentage"] for quality in ("excellent", "good", "fair", "poor", "critical", "insufficient_data")), 100.0)
        factors = {entry["factor"]: entry["count"] for entry in bucket["primary_factors"]}
        self.assertEqual(factors["CONNECTION_STATUS"], 1)
        self.assertEqual(factors["SIGNAL_STRENGTH"], 1)

    def test_quality_percentages_reflect_insufficient_data_without_treating_it_as_good(self):
        self.record(self.now - timedelta(hours=3), latency_ms=10)
        result = self.explicit()
        target_bucket = result["buckets"][0]
        from .services import evaluate_measurement

        def insufficient(measurement):
            value = evaluate_measurement(measurement)
            value.update(overall_quality="INSUFFICIENT_DATA", primary_factor=None)
            return value

        with patch("apps.network.trends.evaluate_measurement", side_effect=insufficient):
            result = self.explicit()
        bucket = result["buckets"][0]
        self.assertEqual(bucket["insufficient_data"], 1)
        self.assertEqual(bucket["insufficient_data_percentage"], 100.0)
        self.assertEqual(bucket["overall_quality"], "INSUFFICIENT_DATA")
        self.assertNotEqual(target_bucket["overall_quality"], "INSUFFICIENT_DATA")

    def _comparison(self, first_latency, latest_latency):
        early = self.now - timedelta(days=2)
        recent = self.now - timedelta(days=1)
        self.record(early, latency_ms=first_latency)
        self.record(recent, latency_ms=latest_latency)
        return self.explicit()["comparison"]

    def test_comparison_reports_improved_and_percentage_points(self):
        result = self._comparison(250, 10)
        self.assertEqual(result, {"status": "IMPROVED", "first_degraded_percentage": 100.0, "latest_degraded_percentage": 0.0, "change_percentage_points": -100.0})

    def test_comparison_reports_worsened(self):
        result = self._comparison(10, 250)
        self.assertEqual(result["status"], "WORSENED")
        self.assertEqual(result["change_percentage_points"], 100.0)

    def test_comparison_reports_stable(self):
        result = self._comparison(10, 20)
        self.assertEqual(result["status"], "STABLE")
        self.assertEqual(result["change_percentage_points"], 0.0)

    def test_comparison_uses_populated_buckets_only_for_first_and_latest(self):
        early = self.now - timedelta(days=5)
        recent = self.now - timedelta(days=1)
        self.record(early, latency_ms=250)
        self.record(recent, latency_ms=10)
        result = self.explicit()
        self.assertEqual(len(result["buckets"]), 2)
        self.assertEqual(result["comparison"]["status"], "IMPROVED")

    def test_primary_factor_trend_is_evaluator_selected_and_bucket_scoped(self):
        self.record(self.now - timedelta(days=2), packet_loss_percent=4)
        self.record(self.now - timedelta(days=2, minutes=1), latency_ms=1)
        self.record(self.now - timedelta(days=1), signal_strength_dbm=-80)
        result = self.explicit()
        self.assertEqual(len(result["factor_trend"]), 2)
        self.assertEqual(result["factor_trend"][0]["factors"], [{"factor": "PACKET_LOSS", "count": 1}])
        self.assertEqual(result["factor_trend"][1]["factors"], [{"factor": "SIGNAL_STRENGTH", "count": 1}])

    def test_campus_building_location_network_and_device_filters(self):
        self.record(self.now - timedelta(days=2), latency_ms=10, device=self.device)
        self.record(self.now - timedelta(days=1), upload_mbps=4, network=self.other_network, location=self.other_location, device=self.other_device)
        self.record(self.now - timedelta(hours=2), latency_ms=10, network=self.other_campus_network, location=self.other_campus_location)
        for filters, expected in (
            ({"campus": self.campus.pk}, 2),
            ({"building": self.building.pk}, 1),
            ({"location": self.location.pk}, 1),
            ({"network": self.other_network.pk}, 1),
            ({"device": self.device.pk}, 1),
        ):
            result = self.explicit(**filters)
            self.assertEqual(sum(row["total_measurements"] for row in result["buckets"]), expected, filters)

    def test_compatible_combined_filters_narrow_the_same_queryset(self):
        self.record(self.now - timedelta(days=1), latency_ms=10, device=self.device)
        self.record(self.now - timedelta(hours=2), latency_ms=10, network=self.other_network, location=self.other_location, device=self.other_device)
        result = self.explicit(campus=self.campus.pk, building=self.building.pk, location=self.location.pk, network=self.network.pk, device=self.device.pk)
        self.assertEqual(sum(row["total_measurements"] for row in result["buckets"]), 1)

    def test_incompatible_campus_building_location_device_and_network_filters_are_rejected(self):
        cases = (
            {"campus": self.campus.pk, "building": self.other_campus_building.pk},
            {"building": self.building.pk, "location": self.other_location.pk},
            {"location": self.location.pk, "device": self.other_device.pk},
            {"network": self.network.pk, "device": self.other_device.pk},
            {"campus": self.other_campus.pk, "network": self.network.pk},
        )
        for filters in cases:
            with self.subTest(filters=filters), self.assertRaisesRegex(ValueError, "incompatible"):
                self.explicit(**filters)

    def test_invalid_dates_ranges_and_filter_ids_are_rejected(self):
        bad_queries = (
            {"start": self.now.isoformat()},
            {"start": self.now.isoformat(), "end": self.now.isoformat()},
            {"start": "2026-10-01T00:00:00", "end": self.now.isoformat()},
            {"range": "90d"},
            {"device": "not-an-id"},
            {"campus": 0},
            {"source": "synthetic"},
        )
        for query in bad_queries:
            with self.subTest(query=query), self.assertRaises(ValueError):
                get_network_trends(query)

    def test_endpoint_reuses_network_permissions_and_returns_validation_errors(self):
        url = reverse("network-analytics-trends")
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(self.reader)
        self.assertEqual(self.client.get(url, {"start": "bad", "end": self.now.isoformat()}).status_code, 400)
        self.assertEqual(self.client.get(url, {"range": "24h"}).status_code, 200)
