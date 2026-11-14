from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["full_name"]
    list_display = ["full_name", "phone", "role", "is_active"]
    list_filter = ["role", "is_active"]
    search_fields = ["full_name", "phone"]
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Ma'lumot", {"fields": ("full_name", "role", "is_active")}),
        ("Ruxsatlar", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("phone", "full_name", "role", "password1", "password2")}),)
