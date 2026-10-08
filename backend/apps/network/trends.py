"""Descriptive historical trends derived from stored measurements and evaluation v1.0."""

from collections import defaultdict
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.campus.models import Building, Location

from .analytics import (
    QUALITY_LEVELS,
    _empty_counts,
    _overall,
    _percentages,
    _positive_id,
    _window,
)
from .models import Network, NetworkDevice, NetworkMeasurement
from .services import evaluate_measurement


TREND_FILTERS = {"range", "start", "end", "campus", "building", "location", "network", "device"}
QUALITY_FIELDS = {quality: quality.lower() for quality in QUALITY_LEVELS}
DEGRADED_QUALITIES = {"FAIR", "POOR", "CRITICAL"}


class TrendQueryError(ValueError):
    """Invalid trend filters or incompatible campus structure selections."""


def _validate_filters(params):
    unknown = set(params.keys()) - TREND_FILTERS
    if unknown:
        raise TrendQueryError(f"Unsupported trend filter: {sorted(unknown)[0]}.")

    identifiers = {key: _positive_id(params, key) for key in ("campus", "building", "location", "network", "device")}
    campus, building, location, network, device = (identifiers[key] for key in ("campus", "building", "location", "network", "device"))

    def require_related(selected, model, **lookups):
        if selected and not model.objects.filter(pk=selected, **lookups).exists():
            raise TrendQueryError("The selected filters refer to incompatible campus, building, location, network, or device records.")

    if campus and building:
        require_related(building, Building, campus_id=campus)
    if building and location:
        require_related(location, Location, building_id=building)
    if location and device:
        require_related(device, NetworkDevice, location_id=location)
    if network and device:
        require_related(device, NetworkDevice, network_id=network)
    if campus and network:
        require_related(network, Network, campus_id=campus)
    if campus and device:
        require_related(device, NetworkDevice, network__campus_id=campus)
    if building and device:
        require_related(device, NetworkDevice, location__building_id=building)
    if building and network:
        building_campus = Building.objects.filter(pk=building).values_list("campus_id", flat=True).first()
        if not Network.objects.filter(pk=network, campus_id=building_campus).filter(Q(building__isnull=True) | Q(building_id=building)).exists():
            raise TrendQueryError("The selected filters refer to incompatible campus, building, location, network, or device records.")

    return identifiers


def _bucket_start(measured_at, bucket_size):
    local = timezone.localtime(measured_at)
    if bucket_size == "hour":
        return local.replace(minute=0, second=0, microsecond=0)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _new_bucket(timestamp):
    return {
        "bucket": timestamp.isoformat(),
        "total_measurements": 0,
        **{field: 0 for field in QUALITY_FIELDS.values()},
        "degraded": 0,
        "poor_or_critical": 0,
        "latest_measurement_at": None,
        "overall_quality": "INSUFFICIENT_DATA",
        "primary_factors": defaultdict(int),
        "_quality_counts": _empty_counts(),
        "_latest_at": None,
    }


def _finalize_bucket(bucket):
    counts = bucket.pop("_quality_counts")
    bucket["overall_quality"] = _overall(counts)
    percentages = _percentages(counts, bucket["total_measurements"])
    for quality, field in QUALITY_FIELDS.items():
        bucket[f"{field}_percentage"] = percentages[quality]
    bucket["degraded_percentage"] = round(bucket["degraded"] * 100 / bucket["total_measurements"], 2)
    bucket["primary_factors"] = [
        {"factor": factor, "count": count}
        for factor, count in sorted(bucket["primary_factors"].items(), key=lambda item: (-item[1], item[0]))
    ]
    bucket.pop("_latest_at")
    return bucket


def _comparison(buckets):
    if not buckets:
        return {"status": "NO_DATA", "first_degraded_percentage": None, "latest_degraded_percentage": None, "change_percentage_points": None}
    if len(buckets) < 2:
        return {"status": "NO_COMPARISON", "first_degraded_percentage": None, "latest_degraded_percentage": None, "change_percentage_points": None}

    first = buckets[0]["degraded_percentage"]
    latest = buckets[-1]["degraded_percentage"]
    change = round(latest - first, 2)
    direction = "IMPROVED" if change < 0 else "WORSENED" if change > 0 else "STABLE"
    return {
        "status": direction,
        "first_degraded_percentage": first,
        "latest_degraded_percentage": latest,
        "change_percentage_points": change,
    }


def get_network_trends(params, now=None):
    """Return populated time buckets only; no zero-filled or synthetic history."""
    start, end, selected_range = _window(params, now)
    identifiers = _validate_filters(params)
    duration = end - start
    bucket_size = "hour" if duration <= timedelta(hours=24) else "day"

    measurements = NetworkMeasurement.objects.filter(measured_at__gte=start, measured_at__lt=end).select_related(
        "network__campus", "network", "device", "location__building"
    )
    if identifiers["campus"]:
        measurements = measurements.filter(network__campus_id=identifiers["campus"])
    if identifiers["building"]:
        measurements = measurements.filter(location__building_id=identifiers["building"])
    if identifiers["location"]:
        measurements = measurements.filter(location_id=identifiers["location"])
    if identifiers["network"]:
        measurements = measurements.filter(network_id=identifiers["network"])
    if identifiers["device"]:
        measurements = measurements.filter(device_id=identifiers["device"])

    grouped = {}
    for measurement in measurements.order_by("measured_at", "pk").iterator(chunk_size=500):
        evaluation = evaluate_measurement(measurement)
        quality = evaluation["overall_quality"]
        timestamp = _bucket_start(measurement.measured_at, bucket_size)
        bucket = grouped.setdefault(timestamp, _new_bucket(timestamp))
        bucket["total_measurements"] += 1
        bucket[QUALITY_FIELDS[quality]] += 1
        bucket["_quality_counts"][quality] += 1
        if quality in DEGRADED_QUALITIES:
            bucket["degraded"] += 1
        if quality in {"POOR", "CRITICAL"}:
            bucket["poor_or_critical"] += 1
        if quality in DEGRADED_QUALITIES and evaluation["primary_factor"]:
            bucket["primary_factors"][evaluation["primary_factor"]] += 1
        if bucket["_latest_at"] is None or measurement.measured_at > bucket["_latest_at"]:
            bucket["_latest_at"] = measurement.measured_at
            bucket["latest_measurement_at"] = measurement.measured_at.isoformat()

    buckets = [_finalize_bucket(grouped[key]) for key in sorted(grouped)]
    return {
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "range": selected_range,
            "timezone": timezone.get_current_timezone_name(),
        },
        "bucket_size": bucket_size,
        "buckets": buckets,
        "comparison": _comparison(buckets),
        "factor_trend": [{"bucket": bucket["bucket"], "factors": bucket["primary_factors"]} for bucket in buckets],
    }
