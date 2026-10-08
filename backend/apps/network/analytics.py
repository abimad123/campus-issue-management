"""Derived network analytics built from persisted measurements and the Phase 5.2 evaluator."""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from django.utils import timezone

from .models import Network, NetworkDevice, NetworkMeasurement
from .services import EVALUATION_VERSION, LABELS, QUALITY_ORDER, evaluate_measurement


QUALITY_LEVELS = (*QUALITY_ORDER, "INSUFFICIENT_DATA")
WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
FILTERS = {"range", "start", "end", "campus", "building", "location", "network", "device", "device_type", "network_type", "quality", "connection_state", "page"}


class AnalyticsQueryError(ValueError):
    """Invalid time window or unsupported analytics filter."""


def _parse_datetime(value, key):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise AnalyticsQueryError(f"'{key}' must be a valid ISO-8601 datetime with a timezone.")
    if timezone.is_naive(parsed):
        raise AnalyticsQueryError(f"'{key}' must include a timezone offset.")
    return parsed


def _window(params, now=None):
    now = now or timezone.now()
    start_raw, end_raw = params.get("start"), params.get("end")
    if bool(start_raw) != bool(end_raw):
        raise AnalyticsQueryError("Provide both 'start' and 'end' for an explicit time range.")
    if start_raw and end_raw:
        start, end = _parse_datetime(start_raw, "start"), _parse_datetime(end_raw, "end")
        window = "explicit"
    else:
        window = params.get("range", "24h")
        if window not in WINDOWS:
            raise AnalyticsQueryError("'range' must be one of: 24h, 7d, 30d.")
        end, start = now, now - WINDOWS[window]
    if start >= end:
        raise AnalyticsQueryError("'start' must be earlier than 'end'.")
    return timezone.localtime(start), timezone.localtime(end), window


def _positive_id(params, key):
    value = params.get(key)
    if value in (None, ""):
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise AnalyticsQueryError(f"'{key}' must be a positive integer.")
    if value < 1:
        raise AnalyticsQueryError(f"'{key}' must be a positive integer.")
    return value


def _validate_params(params):
    unknown = set(params.keys()) - FILTERS
    if unknown:
        raise AnalyticsQueryError(f"Unsupported analytics filter: {sorted(unknown)[0]}.")
    ids = {key: _positive_id(params, key) for key in ("campus", "building", "location", "network", "device")}
    quality = params.get("quality")
    if quality and quality not in QUALITY_LEVELS:
        raise AnalyticsQueryError(f"'quality' must be one of: {', '.join(QUALITY_LEVELS)}.")
    state = params.get("connection_state")
    if state and state not in NetworkMeasurement.ConnectionState.values:
        raise AnalyticsQueryError("'connection_state' is not a supported connection state.")
    device_type = params.get("device_type")
    if device_type and device_type not in NetworkDevice.Kind.values:
        raise AnalyticsQueryError("'device_type' is not a supported network device type.")
    network_type = params.get("network_type")
    if network_type and network_type not in Network.Kind.values:
        raise AnalyticsQueryError("'network_type' is not a supported network type.")
    return ids, quality


def _empty_counts():
    return {key: 0 for key in QUALITY_LEVELS}


def _percentages(counts, total):
    """Largest-remainder allocation in hundredths guarantees a 100.00% sum."""
    if not total:
        return {key: 0.0 for key in counts}
    exact = {key: Decimal(count) * Decimal(10000) / Decimal(total) for key, count in counts.items()}
    allocated = {key: value.to_integral_value(rounding=ROUND_DOWN) for key, value in exact.items()}
    residual = 10000 - int(sum(allocated.values()))
    order = sorted(counts, key=lambda key: (-(exact[key] - allocated[key]), list(counts).index(key)))
    for key in order[:residual]:
        allocated[key] += 1
    return {key: float((value / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) for key, value in allocated.items()}


def _overall(counts):
    for quality in reversed(QUALITY_ORDER):
        if counts[quality]:
            return quality
    return "INSUFFICIENT_DATA"


def _new_bucket(fields):
    return {**fields, "measurement_count": 0, "quality_counts": _empty_counts(), "poor_count": 0, "critical_count": 0, "latest_measurement": None, "latest_at": None}


def _add(bucket, record, evaluation):
    quality = evaluation["overall_quality"]
    bucket["measurement_count"] += 1
    bucket["quality_counts"][quality] += 1
    bucket["poor_count"] += quality == "POOR"
    bucket["critical_count"] += quality == "CRITICAL"
    if bucket["latest_at"] is None or record.measured_at > bucket["latest_at"] or (record.measured_at == bucket["latest_at"] and record.pk > bucket["latest_measurement"]["id"]):
        bucket["latest_at"] = record.measured_at
        bucket["latest_measurement"] = evaluation["measurement"]


def _finish_bucket(bucket):
    counts = bucket.pop("quality_counts")
    bucket.pop("latest_at")
    bucket["overall_quality"] = _overall(counts)
    percentages = _percentages(counts, bucket["measurement_count"])
    bucket["quality_distribution"] = {quality: {"count": counts[quality], "percentage": percentages[quality]} for quality in QUALITY_LEVELS}
    return bucket


def _sort_name(bucket, key):
    return ((bucket.get(key) or "").casefold(), bucket["id"])


def _build(params, now=None, include=None):
    start, end, window = _window(params, now)
    ids, quality_filter = _validate_params(params)
    queryset = NetworkMeasurement.objects.filter(measured_at__gte=start, measured_at__lt=end).select_related(
        "network__campus", "network__building", "location__building__campus", "device__network", "device__location__building__campus"
    )
    if ids["campus"]:
        queryset = queryset.filter(network__campus_id=ids["campus"])
    if ids["building"]:
        queryset = queryset.filter(location__building_id=ids["building"])
    if ids["location"]:
        queryset = queryset.filter(location_id=ids["location"])
    if ids["network"]:
        queryset = queryset.filter(network_id=ids["network"])
    if ids["device"]:
        queryset = queryset.filter(device_id=ids["device"])
    if params.get("device_type"):
        queryset = queryset.filter(device__kind=params["device_type"])
    if params.get("network_type"):
        queryset = queryset.filter(network__kind=params["network_type"])
    if params.get("connection_state"):
        queryset = queryset.filter(connection_state=params["connection_state"])

    selected_groups = set(include if include is not None else ("campuses", "locations", "buildings", "devices", "networks", "problem_locations", "problem_devices"))
    bucket_groups = selected_groups & {"campuses", "locations", "buildings", "devices", "networks"}
    if "problem_locations" in selected_groups:
        bucket_groups.add("locations")
    if "problem_devices" in selected_groups:
        bucket_groups.add("devices")
    buckets = {name: {} for name in bucket_groups}
    factors = defaultdict(int)
    quality_counts = _empty_counts()
    latest = None
    total = degraded_count = poor_count = critical_count = 0

    # Quality is defined by the Python Phase 5.2 evaluator, so each selected row is
    # evaluated once and grouped in one pass. select_related prevents per-row lookups.
    for record in queryset.order_by("measured_at", "pk").iterator(chunk_size=500):
        evaluation = evaluate_measurement(record)
        quality = evaluation["overall_quality"]
        if quality_filter and quality != quality_filter:
            continue
        total += 1
        quality_counts[quality] += 1
        poor_count += quality == "POOR"
        critical_count += quality == "CRITICAL"
        if quality in ("FAIR", "POOR", "CRITICAL"):
            degraded_count += 1
            if evaluation["primary_factor"]:
                factors[evaluation["primary_factor"]] += 1
        if latest is None or (record.measured_at, record.pk) > latest[0]:
            latest = ((record.measured_at, record.pk), evaluation["measurement"], quality, record)

        grouping = []
        location = record.location
        building = location.building
        if "locations" in selected_groups or "problem_locations" in selected_groups:
            grouping.append(("locations", location.pk, {"id": location.pk, "location_name": location.name, "building_id": location.building_id, "building_name": building.name if building else None}))
        if building and "buildings" in selected_groups:
            grouping.append(("buildings", building.pk, {"id": building.pk, "building_name": building.name, "campus_id": building.campus_id, "campus_name": building.campus.name}))
        device = record.device
        if device and ("devices" in selected_groups or "problem_devices" in selected_groups):
            grouping.append(("devices", device.pk, {"id": device.pk, "device_code": device.device_code, "device_name": device.name, "device_type": device.kind, "location_id": device.location_id, "location_name": device.location.display_name, "network_id": device.network_id}))
        network = record.network
        if "campuses" in selected_groups:
            campus = network.campus
            grouping.append(("campuses", campus.pk, {"id": campus.pk, "campus_name": campus.name}))
        if "networks" in selected_groups:
            grouping.append(("networks", network.pk, {"id": network.pk, "network_name": network.name, "network_type": network.kind, "campus_id": network.campus_id, "campus_name": network.campus.name}))
        for group_name, group_id, fields in grouping:
            bucket = buckets[group_name].setdefault(group_id, _new_bucket(fields))
            _add(bucket, record, evaluation)

    group_results = {name: [_finish_bucket(row) for row in rows.values()] for name, rows in buckets.items()}
    for key, name_key in (("campuses", "campus_name"), ("locations", "location_name"), ("buildings", "building_name"), ("devices", "device_code"), ("networks", "network_name")):
        if key in group_results:
            group_results[key].sort(key=lambda row, field=name_key: _sort_name(row, field))
    problem_locations = [row for row in group_results.get("locations", []) if row["poor_count"] or row["critical_count"]]
    problem_devices = [row for row in group_results.get("devices", []) if row["poor_count"] or row["critical_count"]]
    problem_sort = lambda row: (-row["critical_count"], -row["poor_count"], -datetime.fromisoformat(row["latest_measurement"]["measured_at"]).timestamp(), row["id"])
    problem_locations.sort(key=problem_sort)
    problem_devices.sort(key=problem_sort)
    factors_out = [{"factor": factor, "count": factors[factor], "percentage_of_degraded_measurements": round(factors[factor] * 100 / degraded_count, 2) if degraded_count else 0.0} for factor in sorted(factors, key=lambda key: (-factors[key], key))]
    window_data = {"start": start.isoformat(), "end": end.isoformat(), "range": window, "timezone": timezone.get_current_timezone_name()}
    percentages = _percentages(quality_counts, total)
    summary = {
        "window": window_data,
        "total_measurements": total,
        "overall_quality": _overall(quality_counts),
        "quality_distribution": {quality: {"count": quality_counts[quality], "percentage": percentages[quality]} for quality in QUALITY_LEVELS},
        "poor_count": poor_count,
        "critical_count": critical_count,
        "insufficient_data_count": quality_counts["INSUFFICIENT_DATA"],
        "degraded_measurement_count": degraded_count,
        "latest_measurement": {**latest[1], "device_name": latest[3].device.name if latest[3].device_id else None, "device_type": latest[3].device.kind if latest[3].device_id else None, "network_type": latest[3].network.kind, "quality": latest[2], "evaluation_version": EVALUATION_VERSION} if latest else None,
        "primary_factors": factors_out,
        "evaluation_version": EVALUATION_VERSION,
    }
    result = {"window": window_data, "summary": summary}
    result.update(group_results)
    if "problem_locations" in selected_groups:
        result["problem_locations"] = problem_locations
    if "problem_devices" in selected_groups:
        result["problem_devices"] = problem_devices
    return result


def get_network_analytics(params, now=None, include=None):
    """Build a single coherent analytics result from the selected measurements."""
    return _build(params, now=now, include=include)
