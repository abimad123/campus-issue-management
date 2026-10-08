from rest_framework import viewsets
from rest_framework.filters import SearchFilter

from apps.users.permissions import IsCampusAdministrator

from .models import Building, Campus, Department, Location, Team
from .serializers import BuildingSerializer, CampusSerializer, DepartmentSerializer, LocationSerializer, TeamSerializer


class ReadOrCampusAdmin(viewsets.ModelViewSet):
    permission_classes = []

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            from rest_framework.permissions import IsAuthenticated
            return [IsAuthenticated()]
        return [IsCampusAdministrator()]


class CampusViewSet(ReadOrCampusAdmin):
    queryset = Campus.objects.filter(is_active=True)
    serializer_class = CampusSerializer


class BuildingViewSet(ReadOrCampusAdmin):
    serializer_class = BuildingSerializer

    def get_queryset(self):
        return Building.objects.filter(is_active=True).select_related("campus")


class LocationViewSet(ReadOrCampusAdmin):
    serializer_class = LocationSerializer
    filter_backends = [SearchFilter]
    search_fields = ["name", "code", "building__name", "building__campus__name"]

    def get_queryset(self):
        return Location.objects.filter(is_active=True).select_related("building__campus", "parent")


class DepartmentViewSet(ReadOrCampusAdmin):
    queryset = Department.objects.filter(is_active=True)
    serializer_class = DepartmentSerializer


class TeamViewSet(ReadOrCampusAdmin):
    queryset = Team.objects.filter(is_active=True).select_related("department").prefetch_related("members")
    serializer_class = TeamSerializer
