"""Markaz Telegram boti — ota-onalar va o'qituvchilar uchun bitta bot.

/start → "Telefon raqamni yuborish" → raqam bazada kimga tegishli bo'lsa, o'sha rolda ulanadi:
- ota-ona: 📅 Davomat, 💰 To'lov;
- o'qituvchi: 📋 Davomat olish (teacher_bot.py).
"""

from __future__ import annotations

import logging

from apps.academics.models import Attendance, Parent, Student
from apps.accounts.models import User
from apps.core.models import Setting
from apps.core.utils import format_sum, normalize_phone

from .clients import SendError, TelegramClient
from .services import fmt_date, month_name
from .teacher_bot import BTN_TAKE_ATTENDANCE, TeacherFlow, lessons_menu, teacher_by_chat

log = logging.getLogger(__name__)

BTN_ATTENDANCE = "📅 Davomat"
BTN_PAYMENT = "💰 To'lov"

CONTACT_KEYBOARD = {
    "keyboard": [[{"text": "📱 Telefon raqamni yuborish", "request_contact": True}]],
    "resize_keyboard": True,
    "one_time_keyboard": True,
}


def main_keyboard(is_teacher: bool, is_parent: bool) -> dict:
    rows = []
    if is_teacher:
        rows.append([{"text": BTN_TAKE_ATTENDANCE}])
    if is_parent:
        rows.append([{"text": BTN_ATTENDANCE}, {"text": BTN_PAYMENT}])
    return {"keyboard": rows, "resize_keyboard": True}

STATUS_ICON = {"present": "✅", "absent": "❌", "excused": "🟡", "late": "⏰"}


def children_of(chat_id: int) -> list[Student]:
    return list(Student.objects.filter(parents__telegram_chat_id=chat_id).distinct().order_by("full_name"))


def attendance_text(students: list[Student]) -> str:
    parts = []
    for s in students:
        rows = (
            Attendance.objects.filter(student=s).select_related("lesson", "lesson__group")
            .order_by("-lesson__date", "-lesson__start_time")[:10]
        )
        lines = [f"<b>{s.full_name}</b> — oxirgi darslar:"]
        lines += [
            f"{STATUS_ICON.get(a.status, '')} {fmt_date(a.lesson.date)} {a.lesson.group.name}: {a.get_status_display()}"
            for a in rows
        ] or ["Hali davomat yo'q"]
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def payment_text(students: list[Student]) -> str:
    from apps.finance.billing import student_balance
    from apps.finance.models import Invoice

    parts = []
    for s in students:
        balance = student_balance(s)
        lines = [f"<b>{s.full_name}</b>"]
        open_invoices = (
            Invoice.objects.filter(enrollment__student=s, status__in=[Invoice.Status.OPEN, Invoice.Status.PARTIAL])
            .select_related("enrollment__group").order_by("period")
        )
        for inv in open_invoices:
            lines.append(f"• {month_name(inv.period)}, {inv.enrollment.group.name}: qarz {format_sum(inv.debt)} "
                         f"(muddat {fmt_date(inv.due_date)})")
        if balance < 0:
            lines.append(f"Jami qarz: <b>{format_sum(-balance)}</b>")
        elif balance > 0:
            lines.append(f"Avans: {format_sum(balance)}")
        else:
            lines.append("Qarz yo'q ✅")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


class CenterBot:
    def __init__(self, api: TelegramClient | None = None):
        self.api = api or TelegramClient()

    def reply(self, chat_id: int, text: str, keyboard: dict | None = None):
        extra = {"parse_mode": "HTML"}
        if keyboard:
            extra["reply_markup"] = keyboard
        self.api.send_message(chat_id, text, **extra)

    def handle_update(self, update: dict) -> None:
        if "callback_query" in update:
            return self.on_callback(update["callback_query"])
        msg = update.get("message")
        if not msg or msg.get("chat", {}).get("type") != "private":
            return
        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip()

        if "contact" in msg:
            return self.on_contact(chat_id, msg)

        teacher = teacher_by_chat(chat_id)
        students = children_of(chat_id)
        keyboard = main_keyboard(bool(teacher), bool(students))
        if not teacher and not students:
            center = Setting.get("center_name")
            return self.reply(
                chat_id,
                f"Assalomu alaykum! Bu {center} boti.\nDavom etish uchun telefon raqamingizni yuboring "
                "(markazda yozilgan raqam bo'lishi kerak).",
                CONTACT_KEYBOARD,
            )
        if teacher and text == BTN_TAKE_ATTENDANCE:
            menu_text, inline = lessons_menu(teacher)
            return self.reply(chat_id, menu_text, inline or keyboard)
        if students and text == BTN_ATTENDANCE:
            return self.reply(chat_id, attendance_text(students), keyboard)
        if students and text == BTN_PAYMENT:
            return self.reply(chat_id, payment_text(students), keyboard)
        return self.reply(chat_id, "Kerakli bo'limni tanlang.", keyboard)

    def on_callback(self, cq: dict) -> None:
        msg = cq.get("message") or {}
        chat_id = msg.get("chat", {}).get("id")
        teacher = teacher_by_chat(cq.get("from", {}).get("id"))
        if not teacher or chat_id != cq["from"]["id"]:
            self.api.call("answerCallbackQuery", callback_query_id=cq["id"], text="Ruxsat yo'q", show_alert=True)
            return
        notice, text, inline = TeacherFlow(teacher).handle(cq.get("data", ""))
        self.api.call("answerCallbackQuery", callback_query_id=cq["id"], text=notice[:200],
                      show_alert=bool(notice) and text is None)
        if text is not None:
            params = {"chat_id": chat_id, "message_id": msg["message_id"], "text": text, "parse_mode": "HTML"}
            if inline:
                params["reply_markup"] = inline
            try:
                self.api.call("editMessageText", **params)
            except SendError as exc:
                if "not modified" not in str(exc):
                    raise

    def on_contact(self, chat_id: int, msg: dict) -> None:
        contact = msg["contact"]
        # Faqat o'z raqamini yuborishi mumkin — boshqa odamning kontaktini yuborib ulana olmaydi
        if contact.get("user_id") != msg.get("from", {}).get("id"):
            return self.reply(chat_id, "Iltimos, tugma orqali o'zingizning raqamingizni yuboring.", CONTACT_KEYBOARD)
        phone = normalize_phone(contact.get("phone_number", ""))
        parents = Parent.objects.filter(phone=phone) if phone else Parent.objects.none()
        teachers = [u for u in User.objects.filter(role=User.Role.TEACHER, is_active=True)
                    if phone and normalize_phone(u.phone) == phone]
        if not parents.exists() and not teachers:
            return self.reply(
                chat_id,
                "Bu raqam markaz bazasida topilmadi. Iltimos, administratorga murojaat qiling.",
                {"remove_keyboard": True},
            )
        lines = ["✅ Ulandi!"]
        if teachers:
            User.objects.filter(pk__in=[u.pk for u in teachers]).update(telegram_chat_id=chat_id)
            lines.append(f"O'qituvchi: {teachers[0].full_name}. Davomatni '{BTN_TAKE_ATTENDANCE}' tugmasi orqali olasiz.")
        if parents.exists():
            parents.update(telegram_chat_id=chat_id)
            names = ", ".join(s.full_name for s in children_of(chat_id))
            lines.append(f"Farzandlaringiz: {names}. Davomat va to'lov xabarlari shu yerga keladi.")
        log.info("Botga ulandi: chat=%s", chat_id)
        self.reply(chat_id, "\n".join(lines), main_keyboard(bool(teachers), parents.exists()))


ParentBot = CenterBot  # eski nom
