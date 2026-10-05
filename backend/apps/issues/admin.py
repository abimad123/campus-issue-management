from django.contrib import admin

from .models import Issue, IssueAttachment, IssueCategory, IssueEvent


@admin.register(IssueCategory)
class IssueCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


class IssueAttachmentInline(admin.TabularInline):
    model = IssueAttachment
    extra = 0
    readonly_fields = ("file", "content_type", "uploaded_by", "created_at")


class IssueEventInline(admin.TabularInline):
    model = IssueEvent
    extra = 0
    can_delete = False
    readonly_fields = ("actor", "from_status", "to_status", "note", "created_at")


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("ticket_number", "title", "category", "priority", "status", "reporter", "created_at")
    list_filter = ("status", "priority", "category", "location__building", "created_at")
    search_fields = ("ticket_number", "title", "description", "reporter__email", "reporter__full_name")
    readonly_fields = ("ticket_number", "created_at", "updated_at", "resolved_at", "closed_at")
    list_select_related = ("category", "location", "reporter", "assigned_team", "assigned_to")
    inlines = (IssueAttachmentInline, IssueEventInline)

