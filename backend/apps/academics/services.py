"""Guruh, jadval, dars va davomat bo'yicha biznes-logika."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import AuditLog, Setting

from .models import Attendance, Enrollment, Group, GroupSchedule, Lesson


# ---------------------------------------------------------------- sana yordamchilari


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def scheduled_dates(weekdays: set[int], start: date, end: date) -> list[date]:
    """[start, end] oralig'ida (ikkala chegara ham kiradi) jadvaldagi dars kunlari."""
    if start > end or not weekdays:
        return []
    out, d = [], start
    while d <= end:
        if d.weekday() in weekdays:
            out.append(d)
        d += timedelta(days=1)
    return out


def group_weekdays(group: Group) -> set[int]:
    return set(group.schedule.values_list("weekday", flat=True))


# ---------------------------------------------------------------- to'qnashuv nazorati


def _overlaps(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    return a_start < b_end and b_start < a_end


def find_schedule_conflicts(slot: GroupSchedule) -> list[str]:
    """Shu hafta kuni va vaqtda xona yoki o'qituvchi band bo'lsa — xabarlar ro'yxati."""
    group = slot.group
    others = (
        GroupSchedule.objects.filter(weekday=slot.weekday, group__status=Group.Status.ACTIVE)
        .filter(Q(group__room_id=group.room_id) | Q(group__teacher_id=group.teacher_id))
        .exclude(pk=slot.pk)
        .select_related("group", "group__room", "group__teacher")
    )
    messages = []
    for o in others:
        if not _overlaps(slot.start_time, slot.end_time, o.start_time, o.end_time):
            continue
        if o.group_id == group.id:
            messages.append(f"'{group}' guruhida bu vaqtda boshqa dars bor")
            continue
        when = f"{o.get_weekday_display()} {o.start_time:%H:%M}-{o.end_time:%H:%M}"
        if o.group.room_id == group.room_id:
            messages.append(f"'{o.group.room}' xonasi {when} da '{o.group}' guruhi bilan band")
        if o.group.teacher_id == group.teacher_id:
            messages.append(f"O'qituvchi {o.group.teacher} {when} da '{o.group}' guruhida dars beradi")
    return messages


def find_lesson_conflicts(group: Group, room_id: int, day: date, start: time, end: time,
                          exclude_pk: int | None = None) -> list[str]:
    qs = (
        Lesson.objects.filter(date=day)
        .exclude(status=Lesson.Status.CANCELLED)
        .filter(Q(room_id=room_id) | Q(group__teacher_id=group.teacher_id))
        .select_related("group", "room")
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    messages = []
    for o in qs:
        if not _overlaps(start, end, o.start_time, o.end_time):
            continue
        if o.room_id == room_id:
            messages.append(f"'{o.room}' xonasi {day} {o.start_time:%H:%M} da '{o.group}' bilan band")
        if o.group.teacher_id == group.teacher_id:
            messages.append(f"O'qituvchi {day} {o.start_time:%H:%M} da '{o.group}' guruhida band")
    return messages


# ---------------------------------------------------------------- darslar


def generate_lessons(group: Group, start: date, end: date) -> int:
    """Jadvaldan darslarni yaratadi. Qayta chaqirilsa, bor darslarni takrorlamaydi."""
    start = max(start, group.start_date)
    if group.end_date:
        end = min(end, group.end_date)
    created = 0
    slots = list(group.schedule.all())
    for d in scheduled_dates({s.weekday for s in slots}, start, end):
        for s in slots:
            if s.weekday != d.weekday():
                continue
            _, was_created = Lesson.objects.get_or_create(
                group=group, date=d, start_time=s.start_time,
                defaults={"end_time": s.end_time, "room_id": group.room_id},
            )
            created += was_created
    return created


@transaction.atomic
def cancel_lesson(lesson: Lesson, *, user, makeup_date: date, start: time, end: time,
                  room_id: int | None = None) -> Lesson:
    """Darsni bekor qilib, o'rniga qo'shimcha dars qo'yadi. Oylik summa o'zgarmaydi."""
    if lesson.status == Lesson.Status.CANCELLED:
        raise ValidationError("Bu dars allaqachon bekor qilingan")
    if lesson.status == Lesson.Status.DONE or lesson.attendance.exists():
        raise ValidationError("Davomat olingan darsni bekor qilib bo'lmaydi")
    room_id = room_id or lesson.room_id
    conflicts = find_lesson_conflicts(lesson.group, room_id, makeup_date, start, end, exclude_pk=lesson.pk)
    if conflicts:
        raise ValidationError("To'qnashuv: " + "; ".join(conflicts))

    lesson.status = Lesson.Status.CANCELLED
    lesson.save(update_fields=["status"])
    makeup = Lesson.objects.create(
        group=lesson.group, room_id=room_id, date=makeup_date, start_time=start, end_time=end,
        kind=Lesson.Kind.MAKEUP, replaces=lesson,
    )
    AuditLog.record(user, "cancel_lesson", lesson, after={"makeup_lesson_id": makeup.pk})
    return makeup


# ---------------------------------------------------------------- davomat


def attendance_window(lesson: Lesson) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    before = timedelta(minutes=Setting.get_int("attendance_open_before_min"))
    after = timedelta(minutes=Setting.get_int("attendance_close_after_min"))
    opens = timezone.make_aware(datetime.combine(lesson.date, lesson.start_time), tz) - before
    closes = timezone.make_aware(datetime.combine(lesson.date, lesson.end_time), tz) + after
    return opens, closes


def students_of_lesson(lesson: Lesson):
    return [
        e.student
        for e in Enrollment.objects.filter(group=lesson.group, joined_at__lte=lesson.date)
        .filter(Q(left_at__isnull=True) | Q(left_at__gte=lesson.date))
        .select_related("student")
    ]


@dataclass
class AttendanceItem:
    student_id: int
    status: str


@transaction.atomic
def mark_attendance(lesson: Lesson, user, items: list[AttendanceItem],
                    marked_at: datetime | None = None, now: datetime | None = None) -> list[Attendance]:
    """O'qituvchi yoki admin davomat belgilaydi.

    - O'qituvchi: faqat o'z guruhi, faqat dars oynasi ichida, faqat bir marta.
      `marked_at` — telefonda belgilangan vaqt (oflayn yuborilgan bo'lsa ham to'g'ri tekshiriladi).
    - Admin: istalgan vaqtda o'zgartira oladi, har bir o'zgarish audit logga yoziladi.
    Qaytaradi: yangi yaratilgan yoki o'zgargan yozuvlar (xabarnoma yuborish uchun).
    """
    now = now or timezone.now()
    marked_at = marked_at or now
    if lesson.status == Lesson.Status.CANCELLED:
        raise ValidationError("Bekor qilingan darsga davomat olinmaydi")

    allowed = {s.id for s in students_of_lesson(lesson)}
    valid_status = set(Attendance.Status.values)
    for it in items:
        if it.student_id not in allowed:
            raise ValidationError(f"O'quvchi #{it.student_id} bu guruhda emas")
        if it.status not in valid_status:
            raise ValidationError(f"Noto'g'ri holat: {it.status}")

    if not user.is_admin:
        if lesson.group.teacher_id != user.id:
            raise PermissionDenied("Bu guruh sizniki emas")
        if marked_at > now + timedelta(minutes=5):
            raise ValidationError("Belgilangan vaqt kelajakda bo'lishi mumkin emas")
        opens, closes = attendance_window(lesson)
        if not (opens <= marked_at <= closes):
            raise ValidationError("Davomat faqat dars vaqtida olinadi. O'zgartirish uchun adminga murojaat qiling")

    existing = {a.student_id: a for a in Attendance.objects.select_for_update().filter(lesson=lesson)}
    changed = []
    for it in items:
        rec = existing.get(it.student_id)
        if rec is None:
            rec = Attendance.objects.create(
                lesson=lesson, student_id=it.student_id, status=it.status, marked_by=user, marked_at=marked_at
            )
            changed.append(rec)
        elif rec.status != it.status:
            if not user.is_admin:
                raise PermissionDenied("Saqlangan davomatni faqat admin o'zgartira oladi")
            before = rec.status
            rec.status, rec.updated_by, rec.updated_at = it.status, user, now
            rec.save(update_fields=["status", "updated_by", "updated_at"])
            AuditLog.record(user, "update_attendance", rec, before={"status": before}, after={"status": it.status})
            changed.append(rec)

    if lesson.status == Lesson.Status.PLANNED:
        lesson.status = Lesson.Status.DONE
        lesson.save(update_fields=["status"])

    from apps.notifications.services import notify_attendance

    notify_attendance(changed)  # kelmadi / kechikdi → ota-onaga xabar navbatga
    return changed
