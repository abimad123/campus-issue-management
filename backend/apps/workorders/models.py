from django.conf import settings
from django.db import models

from apps.issues.validators import validate_issue_image


def work_order_attachment_path(instance, filename):
    return f"work-order-evidence/{instance.work_order_id}/{filename}"


class WorkOrder(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        ACCEPTED = "ACCEPTED", "Accepted"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        VERIFIED = "VERIFIED", "Verified"
        REWORK = "REWORK", "Rework required"
        CANCELLED = "CANCELLED", "Cancelled"
        CLOSED = "CLOSED", "Closed"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    number = models.CharField(max_length=32, unique=True, null=True, blank=True, editable=False)
    issue = models.ForeignKey("issues.Issue", on_delete=models.CASCADE, related_name="work_orders")
    team = models.ForeignKey("campus.Team", on_delete=models.PROTECT, related_name="work_orders")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_orders")
    title = models.CharField(max_length=160)
    instructions = models.TextField(blank=True, max_length=5000)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ASSIGNED, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_orders_created")
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_orders_completed")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_orders_verified")
    resolution_summary = models.TextField(blank=True, max_length=5000)
    cancellation_reason = models.CharField(max_length=500, blank=True)
    rework_reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["team", "status"]), models.Index(fields=["assigned_to", "status"])]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.number:
            from django.utils import timezone
            self.number = f"WO-{timezone.localdate():%Y}-{self.pk:06d}"
            super().save(update_fields=["number"])

    def __str__(self):
        return self.number or f"Work order {self.pk or 'new'}"


class WorkOrderAssignment(models.Model):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="assignments")
    team = models.ForeignKey("campus.Team", on_delete=models.PROTECT, related_name="work_order_assignments")
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_assignments")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_assignments_made")
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class WorkOrderEvent(models.Model):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="work_order_events")
    event_type = models.CharField(max_length=40, db_index=True)
    from_status = models.CharField(max_length=16, choices=WorkOrder.Status.choices, blank=True)
    to_status = models.CharField(max_length=16, choices=WorkOrder.Status.choices, blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "pk"]


class WorkOrderNote(models.Model):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="work_order_notes")
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at", "pk"]


class WorkOrderMaterial(models.Model):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="materials")
    name = models.CharField(max_length=160)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="work_order_materials")
    created_at = models.DateTimeField(auto_now_add=True)


class WorkOrderEvidence(models.Model):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="evidence")
    file = models.ImageField(upload_to=work_order_attachment_path, validators=[validate_issue_image])
    content_type = models.CharField(max_length=40, editable=False)
    caption = models.CharField(max_length=240, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="work_order_evidence")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def save(self, *args, **kwargs):
        if self.file:
            from PIL import Image
            validate_issue_image(self.file)
            self.file.seek(0)
            with Image.open(self.file) as image:
                self.content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image.format]
            self.file.seek(0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Evidence for {self.work_order}"
