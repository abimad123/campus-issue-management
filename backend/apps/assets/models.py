import uuid

from django.db import models


class Asset(models.Model):
    asset_code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=140)
    asset_type = models.CharField(max_length=80)
    location = models.ForeignKey("campus.Location", on_delete=models.PROTECT, related_name="assets")
    qr_identifier = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_code"]
        indexes = [models.Index(fields=["asset_type", "is_active"])]

    def __str__(self):
        return f"{self.asset_code} · {self.name}"
