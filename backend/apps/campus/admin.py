from django.contrib import admin

from .models import Building, Campus, Department, Location, Team


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "campus", "is_active")
    list_filter = ("campus", "is_active")
    search_fields = ("name", "code")
    list_select_related = ("campus",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "building", "is_active")
    list_filter = ("kind", "building", "is_active")
    search_fields = ("name", "code", "building__name")
    list_select_related = ("building",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "is_active")
    list_filter = ("department", "is_active")
    search_fields = ("name", "department__name")
    filter_horizontal = ("members",)
    list_select_related = ("department",)
