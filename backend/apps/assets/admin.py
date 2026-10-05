from django.contrib import admin

from .models import Asset


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_code", "name", "asset_type", "location", "is_active", "created_at")
    list_filter = ("asset_type", "is_active", "location__building")
    search_fields = ("asset_code", "name", "qr_identifier")
    readonly_fields = ("qr_identifier", "created_at", "updated_at")
    list_select_related = ("location",)
