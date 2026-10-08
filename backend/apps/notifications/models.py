from django.conf import settings
from django.db import models


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=40, db_index=True)
    title = models.CharField(max_length=160)
    message = models.CharField(max_length=500)
    issue = models.ForeignKey("issues.Issue", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

