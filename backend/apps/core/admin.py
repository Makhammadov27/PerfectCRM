from django.contrib import admin

from .models import AuditLog, Setting


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ["key", "value"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["at", "user", "action", "entity", "entity_id"]
    list_filter = ["action", "entity"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
