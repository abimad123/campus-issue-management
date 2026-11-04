from django.conf import settings
from django.db import models


class SlaPolicy(models.Model):
    name = models.CharField(max_length=120)
    active = models.BooleanField(default=True)
    priority_order = models.PositiveIntegerField(default=100, db_index=True)
    category = models.ForeignKey("issues.IssueCategory", null=True, blank=True, on_delete=models.PROTECT)
    issue_priority = models.CharField(max_length=8, choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")], null=True, blank=True)
    response_time_seconds = models.PositiveIntegerField()
    resolution_time_seconds = models.PositiveIntegerField()
    warning_before_seconds = models.PositiveIntegerField(default=1800)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority_order", "-category_id", "-issue_priority", "pk"]
        indexes = [models.Index(fields=["active", "priority_order"])]

    def __str__(self):
        return self.name


class SlaEscalationLevel(models.Model):
    policy = models.ForeignKey(SlaPolicy, on_delete=models.CASCADE, related_name="escalation_levels")
    level = models.PositiveSmallIntegerField()
    after_breach_seconds = models.PositiveIntegerField(default=0)
    recipient_role = models.CharField(max_length=32, choices=[("ADMIN", "Administrator")], default="ADMIN")
    legacy_recipient_role = models.CharField(max_length=32, blank=True, editable=False)

    class Meta:
        ordering = ["level"]
        constraints = [models.UniqueConstraint(fields=["policy", "level"], name="uniq_sla_escalation_level")]


class SlaEvent(models.Model):
    class Type(models.TextChoices):
        STARTED = "SLA_STARTED", "SLA started"
        WARNING = "SLA_WARNING", "SLA warning"
        RESPONSE_WARNING = "RESPONSE_WARNING", "Response deadline warning"
        RESOLUTION_WARNING = "RESOLUTION_WARNING", "Resolution deadline warning"
        RESPONSE_BREACHED = "RESPONSE_BREACHED", "Response breached"
        RESOLUTION_BREACHED = "RESOLUTION_BREACHED", "Resolution breached"
        ESCALATION = "ESCALATION_TRIGGERED", "Escalation triggered"

    issue = models.ForeignKey("issues.Issue", on_delete=models.CASCADE, related_name="sla_events")
    policy = models.ForeignKey(SlaPolicy, null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=32, choices=Type.choices)
    escalation_level = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [models.UniqueConstraint(fields=["issue", "event_type"], condition=models.Q(event_type__in=["SLA_STARTED", "RESPONSE_WARNING", "RESOLUTION_WARNING", "RESPONSE_BREACHED", "RESOLUTION_BREACHED"]), name="uniq_issue_sla_event_once")]
