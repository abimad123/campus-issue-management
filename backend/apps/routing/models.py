from django.conf import settings
from django.db import models


class RoutingRule(models.Model):
    name = models.CharField(max_length=120)
    active = models.BooleanField(default=True)
    priority_order = models.PositiveIntegerField(default=100, db_index=True)
    category = models.ForeignKey("issues.IssueCategory", null=True, blank=True, on_delete=models.PROTECT)
    location = models.ForeignKey("campus.Location", null=True, blank=True, on_delete=models.PROTECT)
    issue_priority = models.CharField(max_length=8, choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")], null=True, blank=True)
    target_team = models.ForeignKey("campus.Team", on_delete=models.PROTECT, related_name="routing_rules")
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="routing_rules")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_routing_rules")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority_order", "-category_id", "-location_id", "-issue_priority", "pk"]
        indexes = [models.Index(fields=["active", "priority_order"])]

    def __str__(self):
        return self.name


class Assignment(models.Model):
    issue = models.ForeignKey("issues.Issue", on_delete=models.CASCADE, related_name="assignments")
    team = models.ForeignKey("campus.Team", null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    routing_rule = models.ForeignKey(RoutingRule, null=True, blank=True, on_delete=models.SET_NULL)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assignments_made")
    reason = models.CharField(max_length=500, blank=True)
    is_automatic = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
