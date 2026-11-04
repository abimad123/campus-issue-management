from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        request = self.context.get("request")
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        identifier = attrs["identifier"].strip()
        user_obj = UserModel.objects.filter(institutional_id__iexact=identifier).first()
        username = user_obj.email if user_obj else identifier.lower()
        user = authenticate(request, username=username, password=attrs["password"])
        if user is None or not user.is_active:
            raise serializers.ValidationError("Institutional ID or email and password are incorrect.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    team_ids = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "institutional_id", "full_name", "phone_number", "role", "technical_specialization", "date_joined", "team_ids")
        read_only_fields = fields

    def get_team_ids(self, obj):
        return list(obj.teams.values_list("id", flat=True))
