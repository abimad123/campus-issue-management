from rest_framework import serializers
from .models import Assignment, RoutingRule


class RoutingRuleSerializer(serializers.ModelSerializer):
    target_team_name = serializers.CharField(source="target_team.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True, allow_null=True)
    location_name = serializers.CharField(source="location.display_name", read_only=True, allow_null=True)
    class Meta:
        model = RoutingRule
        fields = ("id", "name", "active", "priority_order", "category", "category_name", "location", "location_name", "issue_priority", "target_team", "target_team_name", "target_user", "created_by", "created_at", "updated_at")
        read_only_fields = ("created_by", "created_at", "updated_at")

    def validate(self, attrs):
        team = attrs.get("target_team", getattr(self.instance, "target_team", None))
        user = attrs.get("target_user", getattr(self.instance, "target_user", None))
        if user and (not team or not team.members.filter(pk=user.pk, is_active=True).exists()):
            raise serializers.ValidationError({"target_user": "The target user must be an active member of the target team."})
        return attrs


class ManualAssignmentSerializer(serializers.Serializer):
    team = serializers.IntegerField()
    user = serializers.IntegerField()
    reason = serializers.CharField(max_length=500, min_length=3)
