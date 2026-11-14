"""O'qituvchi botda davomat oladi.

📋 Davomat olish → bugungi darslar → dars tanlanadi → har bir o'quvchi tugma:
bosilganda holat almashadi (✅ → ❌ → ⏰ → 🟡) → 💾 Saqlash.
Barcha qoidalar `mark_attendance` da: faqat o'z guruhi, faqat dars vaqtida, saqlangandan keyin faqat admin o'zgartiradi.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.academics.models import Attendance, Group, Lesson
from apps.academics.services import (
    AttendanceItem, attendance_window, generate_lessons, mark_attendance, students_of_lesson,
)
from apps.accounts.models import User

from .models import AttendanceDraft
from .services import fmt_date

BTN_TAKE_ATTENDANCE = "📋 Davomat olish"

STATUS_ICON = {"present": "✅", "absent": "❌", "late": "⏰", "excused": "🟡"}
CYCLE = ["present", "absent", "late", "excused"]
LEGEND = "✅ keldi  ❌ kelmadi  ⏰ kechikdi  🟡 sababli"


def teacher_by_chat(chat_id: int) -> User | None:
    return User.objects.filter(telegram_chat_id=chat_id, role=User.Role.TEACHER, is_active=True).first()


def lesson_title(lesson: Lesson) -> str:
    return f"<b>{lesson.group.name}</b> — {fmt_date(lesson.date)} {lesson.start_time:%H:%M}"


def todays_lessons(teacher: User) -> list[Lesson]:
    today = timezone.localdate()
    for g in Group.objects.filter(teacher=teacher, status=Group.Status.ACTIVE):
        generate_lessons(g, today, today)  # daily_jobs ishlamagan bo'lsa ham bugungi darslar bo'lsin
    return list(
        Lesson.objects.filter(group__teacher=teacher, date=today)
        .exclude(status=Lesson.Status.CANCELLED)
        .select_related("group").order_by("start_time")
    )


def lessons_menu(teacher: User) -> tuple[str, dict | None]:
    lessons = todays_lessons(teacher)
    if not lessons:
        return "Bugun darsingiz yo'q.", None
    rows = []
    for l in lessons:
        mark = "✅" if l.attendance.exists() else "⏳"
        rows.append([{"text": f"{mark} {l.start_time:%H:%M} {l.group.name}", "callback_data": f"L:{l.pk}"}])
    return "Bugungi darslaringiz. Davomat olish uchun darsni tanlang:", {"inline_keyboard": rows}


def draft_view(draft: AttendanceDraft) -> tuple[str, dict]:
    students = {s.id: s for s in students_of_lesson(draft.lesson)}
    rows = []
    for sid, student in sorted(students.items(), key=lambda kv: kv[1].full_name):
        status = draft.statuses.get(str(sid), "present")
        rows.append([{"text": f"{STATUS_ICON[status]} {student.full_name}", "callback_data": f"T:{draft.pk}:{sid}"}])
    rows.append([
        {"text": "✅ Hammasi keldi", "callback_data": f"A:{draft.pk}"},
        {"text": "💾 Saqlash", "callback_data": f"S:{draft.pk}"},
    ])
    absent = sum(1 for s in draft.statuses.values() if s != "present")
    text = (f"{lesson_title(draft.lesson)}\nO'quvchi ustiga bosib holatini o'zgartiring.\n{LEGEND}\n\n"
            f"Jami: {len(students)}, kelmagan/kechikkan: {absent}")
    return text, {"inline_keyboard": rows}


def saved_summary(lesson: Lesson) -> str:
    rows = Attendance.objects.filter(lesson=lesson).select_related("student").order_by("student__full_name")
    lines = [f"{STATUS_ICON[a.status]} {a.student.full_name}" for a in rows]
    return (f"{lesson_title(lesson)}\n✅ Davomat saqlandi.\n\n" + "\n".join(lines) +
            "\n\nO'zgartirish kerak bo'lsa — adminga murojaat qiling.")


class TeacherFlow:
    """Callback tugmalarini qayta ishlaydi. Qaytaradi: (javob matni, tahrirlangan xabar matni, klaviatura)."""

    def __init__(self, teacher: User):
        self.teacher = teacher

    def handle(self, data: str) -> tuple[str, str | None, dict | None]:
        kind, _, rest = data.partition(":")
        if kind == "L":
            return self.open_lesson(int(rest))
        if kind == "M":
            text, kb = lessons_menu(self.teacher)
            return "", text, kb
        draft_id, _, sid = rest.partition(":")
        draft = AttendanceDraft.objects.select_related("lesson__group").filter(
            pk=int(draft_id), teacher=self.teacher
        ).first()
        if draft is None:
            return "Bu ro'yxat eskirgan. Qaytadan '📋 Davomat olish' ni bosing.", None, None
        if kind == "T":
            cur = draft.statuses.get(sid, "present")
            draft.statuses[sid] = CYCLE[(CYCLE.index(cur) + 1) % len(CYCLE)]
            draft.save(update_fields=["statuses", "updated_at"])
            return "", *draft_view(draft)
        if kind == "A":
            draft.statuses = {}
            draft.save(update_fields=["statuses", "updated_at"])
            return "", *draft_view(draft)
        if kind == "S":
            return self.save(draft)
        return "", None, None

    def open_lesson(self, lesson_id: int):
        lesson = Lesson.objects.select_related("group").filter(pk=lesson_id).first()
        if lesson is None or lesson.group.teacher_id != self.teacher.id:
            return "Bu dars sizniki emas", None, None
        if lesson.attendance.exists():
            return "", saved_summary(lesson), None
        opens, closes = attendance_window(lesson)
        now = timezone.now()
        if not (opens <= now <= closes):
            local = timezone.localtime
            return (f"Davomat {local(opens):%H:%M} – {local(closes):%H:%M} oralig'ida olinadi", None, None)
        draft, _ = AttendanceDraft.objects.update_or_create(
            lesson=lesson, teacher=self.teacher, defaults={"statuses": {}}
        )
        return "", *draft_view(draft)

    def save(self, draft: AttendanceDraft):
        lesson = draft.lesson
        items = [AttendanceItem(s.id, draft.statuses.get(str(s.id), "present")) for s in students_of_lesson(lesson)]
        try:
            mark_attendance(lesson, self.teacher, items)
        except (ValidationError, PermissionDenied) as exc:
            msg = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            return msg, None, None
        draft.delete()
        return "Saqlandi ✅", saved_summary(lesson), None
