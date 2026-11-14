from datetime import date, datetime, time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.academics.models import Attendance, GroupSchedule, Lesson, Room
from apps.academics.services import AttendanceItem, cancel_lesson, generate_lessons, mark_attendance
from apps.core.models import AuditLog

from .factories import enroll, make_admin, make_group, make_teacher


def at(d: date, hh: int, mm: int = 0):
    return timezone.make_aware(datetime.combine(d, time(hh, mm)))


class ScheduleConflictTests(TestCase):
    def test_same_room_same_time_is_rejected(self):
        g1 = make_group(name="A")
        g2 = make_group(teacher=make_teacher("+998900000009", "Boshqa"), room=g1.room, weekdays=(), name="B")
        slot = GroupSchedule(group=g2, weekday=0, start_time=time(15, 0), end_time=time(16, 0))
        with self.assertRaisesMessage(ValidationError, "xonasi"):
            slot.full_clean()

    def test_same_teacher_other_room_is_rejected(self):
        g1 = make_group(name="A")
        g2 = make_group(teacher=g1.teacher, weekdays=(), name="B")
        slot = GroupSchedule(group=g2, weekday=2, start_time=time(14, 30), end_time=time(16, 0))
        with self.assertRaisesMessage(ValidationError, "O'qituvchi"):
            slot.full_clean()

    def test_back_to_back_is_allowed(self):
        g1 = make_group(name="A")
        g2 = make_group(teacher=g1.teacher, room=g1.room, weekdays=(), name="B")
        GroupSchedule(group=g2, weekday=0, start_time=time(15, 30), end_time=time(17, 0)).full_clean()


class LessonTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.group = make_group()

    def test_generate_lessons_for_month(self):
        self.assertEqual(generate_lessons(self.group, date(2026, 11, 1), date(2026, 11, 30)), 13)
        self.assertEqual(generate_lessons(self.group, date(2026, 11, 1), date(2026, 11, 30)), 0)

    def test_cancel_creates_makeup(self):
        generate_lessons(self.group, date(2026, 11, 2), date(2026, 11, 2))
        lesson = Lesson.objects.get()
        makeup = cancel_lesson(lesson, user=self.admin, makeup_date=date(2026, 11, 3),
                               start=time(14, 0), end=time(15, 30))
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, Lesson.Status.CANCELLED)
        self.assertEqual((makeup.kind, makeup.replaces_id), (Lesson.Kind.MAKEUP, lesson.id))

    def test_makeup_room_conflict(self):
        other = make_group(teacher=make_teacher("+998900000009", "B"), room=self.group.room,
                           weekdays=(1,), name="Boshqa")
        generate_lessons(other, date(2026, 11, 3), date(2026, 11, 3))  # seshanba 14:00
        generate_lessons(self.group, date(2026, 11, 2), date(2026, 11, 2))
        lesson = Lesson.objects.get(group=self.group)
        with self.assertRaises(ValidationError):
            cancel_lesson(lesson, user=self.admin, makeup_date=date(2026, 11, 3), start=time(14, 0), end=time(15, 0))


class AttendanceTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.group = make_group()
        self.teacher = self.group.teacher
        self.e = enroll(self.group, date(2026, 10, 1))
        generate_lessons(self.group, date(2026, 11, 2), date(2026, 11, 2))
        self.lesson = Lesson.objects.get()
        self.day = self.lesson.date

    def mark(self, user, status="present", when=None, now=None):
        when = when or at(self.day, 14, 5)
        return mark_attendance(self.lesson, user, [AttendanceItem(self.e.student_id, status)],
                               marked_at=when, now=now or when)

    def test_teacher_marks_during_lesson(self):
        self.mark(self.teacher, "late")
        self.assertEqual(Attendance.objects.get().status, "late")
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, Lesson.Status.DONE)

    def test_teacher_cannot_mark_outside_window(self):
        with self.assertRaises(ValidationError):
            self.mark(self.teacher, when=at(self.day, 12, 0))
        with self.assertRaises(ValidationError):
            self.mark(self.teacher, when=at(self.day, 18, 0))

    def test_offline_sync_later_uses_phone_time(self):
        # 14:05 da telefonda belgilandi, internet 20:00 da keldi
        self.mark(self.teacher, when=at(self.day, 14, 5), now=at(self.day, 20, 0))
        self.assertEqual(Attendance.objects.count(), 1)

    def test_other_teacher_forbidden(self):
        with self.assertRaises(PermissionDenied):
            self.mark(make_teacher("+998900000009", "Begona"))

    def test_teacher_cannot_change_saved(self):
        self.mark(self.teacher, "present")
        with self.assertRaises(PermissionDenied):
            self.mark(self.teacher, "absent", when=at(self.day, 14, 10))

    def test_admin_changes_any_time_with_audit(self):
        self.mark(self.teacher, "absent")
        self.mark(self.admin, "excused", when=at(self.day + timedelta(days=3), 10, 0))
        self.assertEqual(Attendance.objects.get().status, "excused")
        self.assertTrue(AuditLog.objects.filter(action="update_attendance").exists())

    def test_student_not_in_group_rejected(self):
        other = enroll(make_group(teacher=make_teacher("+998900000009", "B"), room=Room.objects.create(name="Z"),
                                  name="Boshqa"), date(2026, 10, 1), name="Begona")
        with self.assertRaises(ValidationError):
            mark_attendance(self.lesson, self.teacher, [AttendanceItem(other.student_id, "present")],
                            marked_at=at(self.day, 14, 5), now=at(self.day, 14, 5))
