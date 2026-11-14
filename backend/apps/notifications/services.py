"""Xabarnomalar: navbatga qo'yish va yuborish.

Qoida: ota-ona botga ulangan bo'lsa — Telegram (bepul), aks holda — SMS.
Telegram ishlamasa (bot bloklangan) — avtomatik SMS'ga o'tadi.
"""

from __future__ import annotations

from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.academics.models import Parent, Student
from apps.core.models import Setting
from apps.core.utils import format_sum, normalize_phone

from .clients import EskizClient, SendError, TelegramClient
from .models import Notification

MAX_ATTEMPTS = 3
MONTHS = ["", "yanvar", "fevral", "mart", "aprel", "may", "iyun",
          "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def render(kind: str, **ctx) -> str:
    ctx.setdefault("center", Setting.get("center_name"))
    return Setting.get(f"tpl_{kind}").format(**ctx)


def fmt_date(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def month_name(d: date) -> str:
    return MONTHS[d.month]


def enqueue(student: Student, kind: str, text: str, dedupe_key: str | None = None) -> list[Notification]:
    """Har bir ota-onaga xabar navbatga qo'yiladi. `dedupe_key` takroriy eslatmalarning oldini oladi."""
    created = []
    for i, parent in enumerate(student.parents.all()):
        if parent.telegram_chat_id:
            channel = Notification.Channel.TELEGRAM
        elif normalize_phone(parent.phone):
            channel = Notification.Channel.SMS
        else:
            continue
        key = f"{dedupe_key}:{parent.pk}" if dedupe_key else None
        try:
            with transaction.atomic():
                created.append(Notification.objects.create(
                    parent=parent, student=student, channel=channel, kind=kind, text=text, dedupe_key=key,
                ))
        except IntegrityError:
            pass  # bu eslatma allaqachon yuborilgan
    return created


def _send_one(n: Notification, sms: EskizClient, tg: TelegramClient) -> None:
    n.attempts += 1
    try:
        if n.channel == Notification.Channel.TELEGRAM:
            n.provider_id = tg.send_message(n.parent.telegram_chat_id, n.text)
        else:
            phone = normalize_phone(n.parent.phone)
            if not phone:
                raise SendError("Telefon raqami noto'g'ri", permanent=True)
            n.provider_id = sms.send_sms(phone, n.text)
        n.status, n.sent_at, n.error = Notification.Status.SENT, timezone.now(), ""
    except (SendError, OSError) as exc:
        n.error = str(exc)[:1000]
        permanent = getattr(exc, "permanent", False)
        if permanent or n.attempts >= MAX_ATTEMPTS:
            n.status = Notification.Status.FAILED
            if n.channel == Notification.Channel.TELEGRAM and normalize_phone(n.parent.phone):
                # Telegram ishlamadi → SMS bilan qayta yuboramiz
                Notification.objects.create(parent=n.parent, student=n.student, channel=Notification.Channel.SMS,
                                            kind=n.kind, text=n.text)
                if permanent:
                    Parent.objects.filter(pk=n.parent_id).update(telegram_chat_id=None)
    n.save()


def send_pending(limit: int = 50, sms: EskizClient | None = None, tg: TelegramClient | None = None) -> int:
    sms, tg = sms or EskizClient(), tg or TelegramClient()
    batch = list(
        Notification.objects.filter(status=Notification.Status.PENDING)
        .select_related("parent").order_by("created_at")[:limit]
    )
    for n in batch:
        _send_one(n, sms, tg)
    return len(batch)


# ---------------------------------------------------------------- hodisalar


def notify_attendance(records) -> None:
    for rec in records:
        if rec.status not in ("absent", "late"):
            continue
        lesson = rec.lesson
        text = render(rec.status, student=rec.student.full_name, date=fmt_date(lesson.date), group=lesson.group.name)
        enqueue(rec.student, rec.status, text, dedupe_key=f"att:{lesson.pk}:{rec.student_id}:{rec.status}")


def notify_payment_received(payment, balance: int) -> None:
    text = render("payment_received", student=payment.student.full_name, amount=format_sum(payment.amount),
                  receipt=payment.receipt_no,
                  balance=format_sum(balance) if balance >= 0 else "qarz " + format_sum(-balance))
    enqueue(payment.student, Notification.Kind.PAYMENT_RECEIVED, text, dedupe_key=f"pay:{payment.pk}")


def send_payment_reminders(today: date | None = None) -> int:
    """Har kuni bir marta: muddatdan oldin, muddat kuni va kechikkanda eslatma."""
    from apps.finance.models import Invoice

    today = today or timezone.localdate()
    before = Setting.get_int("reminder_days_before")
    repeat = max(1, Setting.get_int("overdue_repeat_days"))
    count = 0
    invoices = (
        Invoice.objects.filter(status__in=[Invoice.Status.OPEN, Invoice.Status.PARTIAL])
        .select_related("enrollment__student", "enrollment__group")
    )
    for inv in invoices:
        days_left = (inv.due_date - today).days
        if days_left == before:
            kind = Notification.Kind.PAYMENT_SOON
        elif days_left == 0:
            kind = Notification.Kind.PAYMENT_DUE
        elif days_left < 0 and (-days_left) % repeat == 0:
            kind = Notification.Kind.PAYMENT_OVERDUE
        else:
            continue
        student = inv.enrollment.student
        text = render(kind, student=student.full_name, month=month_name(inv.period), amount=format_sum(inv.amount),
                      due=fmt_date(inv.due_date), debt=format_sum(inv.debt))
        count += len(enqueue(student, kind, text, dedupe_key=f"{kind}:{inv.pk}:{today}"))
    return count
