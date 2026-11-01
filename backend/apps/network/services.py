"""Deterministic, explainable evaluation of a single raw network measurement."""

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit
from apps.issues.models import Issue

from .models import IssueNetworkContext, NetworkMeasurement


EVALUATION_VERSION = "1.0"
QUALITY_ORDER = ("EXCELLENT", "GOOD", "FAIR", "POOR", "CRITICAL")
LABELS = {"EXCELLENT": "Excellent", "GOOD": "Good", "FAIR": "Fair", "POOR": "Poor", "CRITICAL": "Critical", "INSUFFICIENT_DATA": "Insufficient data"}

# Metric presentation, evaluator and tie-break priority are intentionally explicit.
PRIORITY = ("CONNECTION_STATUS", "PACKET_LOSS", "LATENCY", "SIGNAL_STRENGTH", "DOWNLOAD_THROUGHPUT", "UPLOAD_THROUGHPUT")
METRICS = (
    ("LATENCY", "Latency", "latency_ms", "ms", "lower", ((30, "EXCELLENT"), (60, "GOOD"), (100, "FAIR"), (200, "POOR"))),
    ("PACKET_LOSS", "Packet loss", "packet_loss_percent", "%", "lower", ((1, "EXCELLENT"), (3, "GOOD"), (5, "FAIR"), (10, "POOR"))),
    ("DOWNLOAD_THROUGHPUT", "Download throughput", "download_mbps", "Mbps", "higher", ((100, "EXCELLENT"), (50, "GOOD"), (20, "FAIR"), (5, "POOR"))),
    ("UPLOAD_THROUGHPUT", "Upload throughput", "upload_mbps", "Mbps", "higher", ((50, "EXCELLENT"), (25, "GOOD"), (10, "FAIR"), (2, "POOR"))),
    ("SIGNAL_STRENGTH", "Signal strength", "signal_strength_dbm", "dBm", "signal", None),
)


def _quality(key, value):
    value = Decimal(str(value))
    if key == "SIGNAL_STRENGTH":
        return ("EXCELLENT" if value >= -50 else "GOOD" if value >= -60 else "FAIR" if value >= -67 else "POOR" if value >= -75 else "CRITICAL")
    for boundary, quality in METRICS[[row[0] for row in METRICS].index(key)][5]:
        if (value <= boundary if key in ("LATENCY", "PACKET_LOSS") else value >= boundary):
            return quality
    return "CRITICAL"


def evaluate_measurement(measurement):
    """Return a stable machine-readable explanation; never fill absent values with zero."""
    metric_results, available = [], {}
    for key, label, field, unit, direction, _ in METRICS:
        value = getattr(measurement, field)
        if value is None:
            metric_results.append({"key": key, "label": label, "value": None, "unit": unit, "quality": None, "status": "UNAVAILABLE", "reason": f"{label} was not recorded; no quality classification is available."})
        else:
            quality = _quality(key, value)
            available[key] = quality
            metric_results.append({"key": key, "label": label, "value": str(value), "unit": unit, "quality": quality, "status": "AVAILABLE", "reason": f"{label} is {LABELS[quality].lower()} under evaluation version {EVALUATION_VERSION}."})

    connection = measurement.connection_state
    status_reason = {
        "CONNECTED": "Connection is connected; this status does not lower measured metric quality.",
        "DEGRADED": "Connection is degraded; overall quality is capped at Fair.",
        "DISCONNECTED": "Connection is disconnected; overall quality is Critical regardless of metric values.",
        "UNKNOWN": "Connection status is unknown and is not used to infer quality.",
    }.get(connection, "Connection status is not assessed.")
    metric_results.append({"key": "CONNECTION_STATUS", "label": "Connection status", "value": connection, "unit": None, "quality": "CRITICAL" if connection == "DISCONNECTED" else "FAIR" if connection == "DEGRADED" else None, "status": connection, "reason": status_reason})

    if connection == "DISCONNECTED":
        overall = "CRITICAL"
    elif not available:
        overall = "INSUFFICIENT_DATA"
    else:
        overall = max(available.values(), key=QUALITY_ORDER.index)
        if connection == "DEGRADED" and QUALITY_ORDER.index(overall) < QUALITY_ORDER.index("FAIR"):
            overall = "FAIR"

    if connection == "DISCONNECTED":
        primary = "CONNECTION_STATUS"
    elif overall == "INSUFFICIENT_DATA":
        primary = None
    elif connection == "DEGRADED" and QUALITY_ORDER.index(max(available.values(), key=QUALITY_ORDER.index)) < QUALITY_ORDER.index("FAIR"):
        primary = "CONNECTION_STATUS"
    else:
        primary = next(key for key in PRIORITY if key in available and available[key] == overall)
    by_key = {item["key"]: item for item in metric_results}
    reasons = [by_key[primary]["reason"]] if primary else ([status_reason] if connection == "UNKNOWN" else [])
    measurement_ref = {"id": measurement.pk, "network": measurement.network_id, "network_name": measurement.network.name, "network_kind": getattr(measurement.network, "kind", None), "device": measurement.device_id, "device_code": measurement.device.device_code if measurement.device_id else None, "device_name": measurement.device.name if measurement.device_id else None, "location": measurement.location_id, "location_name": measurement.location.display_name, "measured_at": measurement.measured_at.isoformat()}
    return {"measurement": measurement_ref, "overall_quality": overall, "overall_label": LABELS[overall], "metrics": metric_results, "primary_factor": primary, "primary_factor_label": by_key[primary]["label"] if primary else None, "reasons": reasons, "evaluation_version": EVALUATION_VERSION}


@transaction.atomic
def attach_network_context(*, issue, measurement, actor):
    """Link a visible issue to a measurement and freeze its current evaluator provenance."""
    issue = Issue.objects.select_for_update().get(pk=issue.pk)
    # The related device and location building are nullable; PostgreSQL cannot
    # lock the nullable side of their outer joins. Lock only the source row.
    measurement = NetworkMeasurement.objects.select_for_update(of=("self",)).select_related(
        "network", "device", "location__building__campus"
    ).get(pk=measurement.pk)
    if IssueNetworkContext.objects.filter(issue=issue, network_measurement=measurement).exists():
        raise ValidationError({"network_measurement": "This network measurement is already attached to this issue."})

    evaluation = evaluate_measurement(measurement)
    context = IssueNetworkContext.objects.create(
        issue=issue,
        network_measurement=measurement,
        created_by=actor,
        evaluator_version=evaluation["evaluation_version"],
        overall_quality=evaluation["overall_quality"],
        primary_factor=evaluation["primary_factor"] or "",
    )
    record_audit(
        "issue.network_context_attached",
        actor=actor,
        entity=issue,
        context={"context_id": context.pk, "network_measurement_id": measurement.pk},
    )
    return context
