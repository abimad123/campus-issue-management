from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(
            request,
            username=attrs["email"].lower(),
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError("Email or password is incorrect.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    team_ids = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "phone_number", "role", "date_joined", "team_ids")
        read_only_fields = fields

    def get_team_ids(self, obj):
        return list(obj.teams.values_list("id", flat=True))
