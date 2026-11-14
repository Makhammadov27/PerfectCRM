from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "parent", "channel", "kind", "status", "attempts"]
    list_filter = ["status", "channel", "kind"]
    search_fields = ["parent__full_name", "parent__phone", "student__full_name"]
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request):
        return False
