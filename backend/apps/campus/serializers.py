from rest_framework import serializers

from .models import Building, Campus, Department, Location, Team


class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ("id", "name", "code", "description", "is_active")


class BuildingSerializer(serializers.ModelSerializer):
    campus_name = serializers.CharField(source="campus.name", read_only=True)

    class Meta:
        model = Building
        fields = ("id", "campus", "campus_name", "name", "code", "description", "is_active")


class LocationSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source="building.name", read_only=True, allow_null=True)
    campus_name = serializers.CharField(source="building.campus.name", read_only=True, allow_null=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Location
        fields = ("id", "building", "building_name", "campus_name", "parent", "name", "code", "kind", "display_name", "description", "is_active")


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name", "code", "description", "is_active")


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ("id", "name", "description", "department", "members", "is_active")
