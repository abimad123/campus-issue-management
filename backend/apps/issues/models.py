from django.conf import settings
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.db import models
from django.utils import timezone

from .validators import issue_attachment_path, validate_issue_image


class IssueCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    icon_identifier = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "issue categories"

    def __str__(self):
        return self.name


class Issue(models.Model):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_REVIEW = "IN_REVIEW", "In review"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"
        REOPENED = "REOPENED", "Reopened"

    ticket_number = models.CharField(max_length=32, unique=True, null=True, blank=True, editable=False)
    title = models.CharField(max_length=160, validators=[MinLengthValidator(4), MaxLengthValidator(160)])
    description = models.TextField(validators=[MinLengthValidator(10), MaxLengthValidator(5000)])
    category = models.ForeignKey(IssueCategory, on_delete=models.PROTECT, related_name="issues")
    location = models.ForeignKey("campus.Location", on_delete=models.PROTECT, related_name="issues")
    asset = models.ForeignKey("assets.Asset", on_delete=models.SET_NULL, related_name="issues", null=True, blank=True)
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reported_issues")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="assigned_issues", null=True, blank=True)
    assigned_team = models.ForeignKey("campus.Team", on_delete=models.SET_NULL, related_name="issues", null=True, blank=True)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    response_at = models.DateTimeField(null=True, blank=True)
    sla_policy = models.ForeignKey("sla.SlaPolicy", null=True, blank=True, on_delete=models.SET_NULL, related_name="issues")
    response_due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    response_breached_at = models.DateTimeField(null=True, blank=True)
    resolution_breached_at = models.DateTimeField(null=True, blank=True)
    current_escalation_level = models.PositiveSmallIntegerField(default=0)
    escalation_started_at = models.DateTimeField(null=True, blank=True)
    next_escalation_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["priority", "created_at"]),
            models.Index(fields=["category", "created_at"]),
            models.Index(fields=["reporter", "created_at"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["assigned_team", "status"]),
        ]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.ticket_number:
            self.ticket_number = f"ISS-{timezone.localdate():%Y}-{self.pk:06d}"
            super().save(update_fields=["ticket_number"])

    def __str__(self):
        return self.ticket_number or f"Issue {self.pk or 'new'}"


class IssueEvent(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="issue_events")
    from_status = models.CharField(max_length=16, choices=Issue.Status.choices, blank=True)
    to_status = models.CharField(max_length=16, choices=Issue.Status.choices)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


class IssueAttachment(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="attachments")
    file = models.ImageField(upload_to=issue_attachment_path, validators=[validate_issue_image])
    content_type = models.CharField(max_length=40, editable=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="issue_attachments")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.file:
            validate_issue_image(self.file)
            from PIL import Image
            self.file.seek(0)
            with Image.open(self.file) as image:
                self.content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image.format]
            self.file.seek(0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attachment for {self.issue}"
