from django.contrib import admin

from .models import Attendance, Enrollment, Group, GroupSchedule, Lesson, Parent, Room, Student


class ParentInline(admin.TabularInline):
    model = Parent
    extra = 1


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["full_name", "phone", "parents__phone"]
    inlines = [ParentInline, EnrollmentInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["name", "capacity"]


class ScheduleInline(admin.TabularInline):
    model = GroupSchedule
    extra = 3


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "subject", "teacher", "room", "monthly_price", "lesson_price", "status"]
    list_filter = ["status", "teacher", "room"]
    search_fields = ["name", "subject"]
    inlines = [ScheduleInline, EnrollmentInline]


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    readonly_fields = ["marked_by", "marked_at", "updated_by", "updated_at"]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["group", "date", "start_time", "room", "status", "kind"]
    list_filter = ["status", "kind", "group"]
    date_hierarchy = "date"
    inlines = [AttendanceInline]
