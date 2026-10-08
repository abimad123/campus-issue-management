from django.contrib import admin

from .models import WorkOrder, WorkOrderAssignment, WorkOrderEvent, WorkOrderEvidence, WorkOrderMaterial, WorkOrderNote


class AssignmentInline(admin.TabularInline):
    model = WorkOrderAssignment
    extra = 0
    readonly_fields = ("created_at",)


class EventInline(admin.TabularInline):
    model = WorkOrderEvent
    extra = 0
    readonly_fields = ("event_type", "from_status", "to_status", "note", "actor", "created_at")
    can_delete = False


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "issue", "team", "assigned_to", "status", "priority", "created_at")
    list_filter = ("status", "priority", "team")
    search_fields = ("number", "title", "issue__ticket_number", "issue__title", "assigned_to__email")
    readonly_fields = ("number", "created_at", "accepted_at", "started_at", "completed_at", "verified_at", "closed_at")
    inlines = (AssignmentInline, EventInline)


admin.site.register(WorkOrderNote)
admin.site.register(WorkOrderMaterial)
admin.site.register(WorkOrderEvidence)
