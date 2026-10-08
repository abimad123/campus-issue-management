from django.db import transaction
from rest_framework import serializers
from .models import SlaEscalationLevel, SlaPolicy


class SlaEscalationLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SlaEscalationLevel
        fields = ("level", "after_breach_seconds", "recipient_role")


class SlaPolicySerializer(serializers.ModelSerializer):
    escalation_levels = SlaEscalationLevelSerializer(many=True, required=False)
    category_name = serializers.CharField(source="category.name", read_only=True, allow_null=True)

    class Meta:
        model = SlaPolicy
        fields = ("id", "name", "active", "priority_order", "category", "category_name", "issue_priority", "response_time_seconds", "resolution_time_seconds", "warning_before_seconds", "escalation_levels", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def validate(self, attrs):
        response = attrs.get("response_time_seconds", getattr(self.instance, "response_time_seconds", 0))
        resolution = attrs.get("resolution_time_seconds", getattr(self.instance, "resolution_time_seconds", 0))
        if response <= 0 or resolution <= 0:
            raise serializers.ValidationError("Response and resolution times must be greater than zero.")
        levels = attrs.get("escalation_levels", [])
        numbers = [item["level"] for item in levels]
        if len(numbers) != len(set(numbers)) or 0 in numbers:
            raise serializers.ValidationError({"escalation_levels": "Use unique escalation levels starting at 1."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        levels = validated_data.pop("escalation_levels", [])
        policy = super().create(validated_data)
        SlaEscalationLevel.objects.bulk_create([SlaEscalationLevel(policy=policy, **level) for level in levels])
        return policy

    @transaction.atomic
    def update(self, instance, validated_data):
        levels = validated_data.pop("escalation_levels", None)
        policy = super().update(instance, validated_data)
        if levels is not None:
            policy.escalation_levels.all().delete()
            SlaEscalationLevel.objects.bulk_create([SlaEscalationLevel(policy=policy, **level) for level in levels])
        return policy
