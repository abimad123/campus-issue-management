from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Network(models.Model):
    class Kind(models.TextChoices):
        WIFI = "WIFI", "Wi-Fi"
        LAN = "LAN", "LAN"
        WAN = "WAN", "WAN"

    campus = models.ForeignKey("campus.Campus", on_delete=models.PROTECT, related_name="networks")
    building = models.ForeignKey("campus.Building", on_delete=models.PROTECT, related_name="networks", null=True, blank=True)
    code = models.SlugField(max_length=32)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["campus__name", "name"]
        constraints = [models.UniqueConstraint(fields=["campus", "code"], name="uniq_network_code_per_campus")]
        indexes = [models.Index(fields=["campus", "kind", "is_active"])]

    def __str__(self):
        return f"{self.name} · {self.campus.name}"


class NetworkDevice(models.Model):
    class Kind(models.TextChoices):
        ACCESS_POINT = "ACCESS_POINT", "Access point"
        SWITCH = "SWITCH", "Switch"
        ROUTER = "ROUTER", "Router"
        GATEWAY = "GATEWAY", "Gateway"

    class State(models.TextChoices):
        DEPLOYED = "DEPLOYED", "Deployed"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        RETIRED = "RETIRED", "Retired"

    device_code = models.CharField(max_length=48, unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    network = models.ForeignKey(Network, on_delete=models.PROTECT, related_name="devices")
    location = models.ForeignKey("campus.Location", on_delete=models.PROTECT, related_name="network_devices")
    asset = models.OneToOneField("assets.Asset", on_delete=models.PROTECT, related_name="network_device", null=True, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.DEPLOYED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["device_code"]
        indexes = [models.Index(fields=["kind", "state"]), models.Index(fields=["network", "state"])]

    def __str__(self):
        return f"{self.device_code} · {self.name}"


class NetworkMeasurement(models.Model):
    class ConnectionState(models.TextChoices):
        CONNECTED = "CONNECTED", "Connected"
        DEGRADED = "DEGRADED", "Degraded"
        DISCONNECTED = "DISCONNECTED", "Disconnected"
        UNKNOWN = "UNKNOWN", "Unknown"

    network = models.ForeignKey(Network, on_delete=models.PROTECT, related_name="measurements")
    location = models.ForeignKey("campus.Location", on_delete=models.PROTECT, related_name="network_measurements")
    device = models.ForeignKey(NetworkDevice, on_delete=models.PROTECT, related_name="measurements", null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="network_measurements")
    measured_at = models.DateTimeField(auto_now_add=True)
    latency_ms = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(60000)])
    packet_loss_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    download_mbps = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(1000000)])
    upload_mbps = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(1000000)])
    signal_strength_dbm = models.SmallIntegerField(null=True, blank=True, validators=[MinValueValidator(-120), MaxValueValidator(0)])
    connection_state = models.CharField(max_length=16, choices=ConnectionState.choices, default=ConnectionState.UNKNOWN)
    note = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["-measured_at", "-pk"]
        indexes = [
            models.Index(fields=["-measured_at"], name="network_msr_measured_idx"),
            models.Index(fields=["network", "-measured_at"]),
            models.Index(fields=["location", "-measured_at"]),
            models.Index(fields=["recorded_by", "-measured_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(latency_ms__isnull=True) | Q(latency_ms__gte=0, latency_ms__lte=60000), name="network_latency_range"),
            models.CheckConstraint(condition=Q(packet_loss_percent__isnull=True) | Q(packet_loss_percent__gte=0, packet_loss_percent__lte=100), name="network_packet_loss_range"),
            models.CheckConstraint(condition=Q(download_mbps__isnull=True) | Q(download_mbps__gte=0, download_mbps__lte=1000000), name="network_download_range"),
            models.CheckConstraint(condition=Q(upload_mbps__isnull=True) | Q(upload_mbps__gte=0, upload_mbps__lte=1000000), name="network_upload_range"),
            models.CheckConstraint(condition=Q(signal_strength_dbm__isnull=True) | Q(signal_strength_dbm__gte=-120, signal_strength_dbm__lte=0), name="network_signal_range"),
            models.CheckConstraint(condition=~Q(latency_ms__isnull=True, packet_loss_percent__isnull=True, download_mbps__isnull=True, upload_mbps__isnull=True, signal_strength_dbm__isnull=True), name="network_measurement_has_metric"),
        ]


class IssueNetworkContext(models.Model):
    """Auditable link from an operational issue to supporting raw network evidence."""

    issue = models.ForeignKey("issues.Issue", on_delete=models.PROTECT, related_name="network_contexts")
    network_measurement = models.ForeignKey(NetworkMeasurement, on_delete=models.PROTECT, related_name="issue_contexts")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="issue_network_contexts")
    created_at = models.DateTimeField(auto_now_add=True)
    evaluator_version = models.CharField(max_length=32)
    overall_quality = models.CharField(max_length=24)
    primary_factor = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["issue", "network_measurement"], name="uniq_issue_network_context"),
        ]
        indexes = [models.Index(fields=["issue", "-created_at"], name="issue_net_context_time_idx")]

    def __str__(self):
        return f"Network measurement {self.network_measurement_id} supporting {self.issue_id}"
