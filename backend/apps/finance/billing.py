"""To'lov hisob-kitobi. Qoidalar: docs/TZ.md, 3-bo'lim.

- To'liq oy → guruhning oylik narxi (oyda 13 dars bo'lsa ham).
- Oy o'rtasida qo'shilgan / ketgan → jadvaldagi darslar × dars narxi, oylik narxdan oshmaydi.
- Pul jadvaldagi barcha darslar uchun olinadi; bekor qilingan dars almashtiriladi, summa o'zgarmaydi.
- Qarz/avans: to'lovlar eng eski hisobdan boshlab yopiladi (FIFO).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.academics.models import Enrollment, Group, Student
from apps.academics.services import group_weekdays, month_bounds, scheduled_dates
from apps.core.models import AuditLog, Setting

from .models import Invoice, Payment, Refund


@dataclass(frozen=True)
class MonthCharge:
    lessons_count: int
    base_amount: int
    discount_amount: int
    amount: int
    full_month: bool


def active_range(enrollment: Enrollment, year: int, month: int) -> tuple[date, date] | None:
    """O'quvchi shu oyda guruhda bo'lgan kunlar oralig'i (ikkala chegara ham kiradi)."""
    first, last = month_bounds(year, month)
    group = enrollment.group
    start = max(first, enrollment.joined_at, group.start_date)
    end = last
    for limit in (enrollment.left_at, group.end_date):
        if limit:
            end = min(end, limit)
    return (start, end) if start <= end else None


def calc_month_charge(enrollment: Enrollment, year: int, month: int,
                      weekdays: set[int] | None = None) -> MonthCharge | None:
    rng = active_range(enrollment, year, month)
    if rng is None:
        return None
    group: Group = enrollment.group
    weekdays = group_weekdays(group) if weekdays is None else weekdays
    first, last = month_bounds(year, month)
    lessons = len(scheduled_dates(weekdays, *rng))
    full_month = rng == (first, last)

    if full_month:
        base = group.monthly_price
    else:
        base = min(lessons * group.lesson_price, group.monthly_price)

    if enrollment.discount_type == Enrollment.DiscountType.PERCENT:
        discount = base * enrollment.discount_value // 100
    elif enrollment.discount_type == Enrollment.DiscountType.FIXED:
        discount = min(enrollment.discount_value, base)
    else:
        discount = 0
    return MonthCharge(lessons, base, discount, base - discount, full_month)


def calc_due_date(enrollment: Enrollment, year: int, month: int) -> date:
    first, last = month_bounds(year, month)
    regular = first.replace(day=min(Setting.get_int("payment_due_day"), last.day))
    if enrollment.joined_at > first:
        return max(regular, enrollment.joined_at + timedelta(days=Setting.get_int("first_invoice_due_days")))
    return regular


@transaction.atomic
def upsert_invoice(enrollment: Enrollment, year: int, month: int) -> Invoice | None:
    """Oy hisobini yaratadi yoki qayta hisoblaydi. O'quvchi shu oyda yo'q bo'lsa — hisob bekor."""
    period = date(year, month, 1)
    charge = calc_month_charge(enrollment, year, month)
    inv = Invoice.objects.filter(enrollment=enrollment, period=period).first()
    if charge is None:
        if inv and inv.status != Invoice.Status.VOID:
            inv.status = Invoice.Status.VOID
            inv.save(update_fields=["status"])
        return inv
    fields = dict(
        lessons_count=charge.lessons_count, base_amount=charge.base_amount,
        discount_amount=charge.discount_amount, amount=charge.amount,
    )
    if inv is None:
        inv = Invoice.objects.create(
            enrollment=enrollment, period=period, due_date=calc_due_date(enrollment, year, month), **fields
        )
    else:
        for k, v in fields.items():
            setattr(inv, k, v)
        if inv.status == Invoice.Status.VOID:
            inv.status = Invoice.Status.OPEN
        inv.save()
    return inv


def generate_month_invoices(year: int, month: int) -> int:
    """Har oy 1-kuni ishga tushadi: barcha faol a'zoliklar uchun hisob."""
    first, last = month_bounds(year, month)
    enrollments = (
        Enrollment.objects.filter(joined_at__lte=last)
        .filter(Q(left_at__isnull=True) | Q(left_at__gte=first))
        .select_related("group", "student")
    )
    students, count = set(), 0
    for e in enrollments:
        if upsert_invoice(e, year, month):
            count += 1
            students.add(e.student_id)
    for sid in students:
        recalc_student(Student.objects.get(pk=sid))
    return count


# ---------------------------------------------------------------- balans


def student_balance(student: Student) -> int:
    """Musbat — avans (ortiqcha to'lov), manfiy — qarz."""
    paid = Payment.objects.filter(student=student, cancelled_at__isnull=True).aggregate(s=Sum("amount"))["s"] or 0
    refunded = Refund.objects.filter(student=student).aggregate(s=Sum("amount"))["s"] or 0
    charged = (
        Invoice.objects.filter(enrollment__student=student)
        .exclude(status=Invoice.Status.VOID)
        .aggregate(s=Sum("amount"))["s"] or 0
    )
    return paid - refunded - charged


@transaction.atomic
def recalc_student(student: Student) -> None:
    """Hisoblarning to'langan qismini qayta taqsimlaydi: eski hisoblar birinchi yopiladi."""
    paid = Payment.objects.filter(student=student, cancelled_at__isnull=True).aggregate(s=Sum("amount"))["s"] or 0
    refunded = Refund.objects.filter(student=student).aggregate(s=Sum("amount"))["s"] or 0
    pool = paid - refunded
    invoices = (
        Invoice.objects.select_for_update()
        .filter(enrollment__student=student)
        .exclude(status=Invoice.Status.VOID)
        .order_by("period", "due_date", "id")
    )
    for inv in invoices:
        covered = max(0, min(inv.amount, pool))
        pool -= covered
        status = (
            Invoice.Status.PAID if covered >= inv.amount
            else Invoice.Status.PARTIAL if covered > 0
            else Invoice.Status.OPEN
        )
        if (inv.paid_amount, inv.status) != (covered, status):
            inv.paid_amount, inv.status = covered, status
            inv.save(update_fields=["paid_amount", "status"])


# ---------------------------------------------------------------- to'lov / qaytarish


def next_receipt_no(now) -> str:
    prefix = f"{now:%y%m}-"
    last = Payment.objects.filter(receipt_no__startswith=prefix).order_by("-receipt_no").first()
    seq = int(last.receipt_no.split("-")[1]) + 1 if last else 1
    return f"{prefix}{seq:05d}"


@transaction.atomic
def accept_payment(student: Student, amount: int, *, user, method=Payment.Method.CASH,
                   note: str = "", paid_at=None) -> Payment:
    if amount <= 0:
        raise ValidationError("Summa 0 dan katta bo'lishi kerak")
    paid_at = paid_at or timezone.now()
    p = Payment.objects.create(
        student=student, amount=amount, method=method, paid_at=paid_at, note=note,
        receipt_no=next_receipt_no(paid_at), received_by=user,
    )
    AuditLog.record(user, "accept_payment", p, after={"amount": amount, "method": method})
    recalc_student(student)

    from apps.notifications.services import notify_payment_received

    notify_payment_received(p, student_balance(student))
    return p


@transaction.atomic
def cancel_payment(payment: Payment, *, user, reason: str) -> Payment:
    """To'lov o'chirilmaydi — bekor qilinadi (sabab bilan)."""
    if payment.is_cancelled:
        raise ValidationError("To'lov allaqachon bekor qilingan")
    if not reason.strip():
        raise ValidationError("Bekor qilish sababini yozing")
    payment.cancelled_at, payment.cancelled_by, payment.cancel_reason = timezone.now(), user, reason
    payment.save(update_fields=["cancelled_at", "cancelled_by", "cancel_reason"])
    AuditLog.record(user, "cancel_payment", payment, before={"amount": payment.amount}, after={"reason": reason})
    recalc_student(payment.student)
    return payment


@transaction.atomic
def process_leave(enrollment: Enrollment, left_at: date, *, user) -> int:
    """O'quvchi guruhdan ketdi: shu oy hisobi qayta hisoblanadi, keyingi oylar bekor qilinadi.

    Qaytaradi: o'quvchiga qaytarish mumkin bo'lgan summa (avans). Pulni berish — `give_refund`.
    """
    if left_at < enrollment.joined_at:
        raise ValidationError("Ketgan sana qo'shilgan sanadan oldin bo'lishi mumkin emas")
    before = {"left_at": str(enrollment.left_at) if enrollment.left_at else None}
    enrollment.left_at = left_at
    enrollment.save(update_fields=["left_at"])

    for inv in enrollment.invoices.filter(period__gte=left_at.replace(day=1)):
        old = inv.amount
        upsert_invoice(enrollment, inv.period.year, inv.period.month)
        inv.refresh_from_db()
        if old != inv.amount or inv.status == Invoice.Status.VOID:
            AuditLog.record(user, "recalc_invoice_leave", inv, before={"amount": old},
                            after={"amount": inv.amount, "status": inv.status})

    AuditLog.record(user, "leave_group", enrollment, before=before, after={"left_at": str(left_at)})
    student = enrollment.student
    if not student.enrollments.filter(Q(left_at__isnull=True) | Q(left_at__gt=left_at)).exists():
        student.status = Student.Status.LEFT
        student.save(update_fields=["status"])
    recalc_student(student)
    return max(0, student_balance(student))


@transaction.atomic
def give_refund(student: Student, amount: int, *, user, reason: str) -> Refund:
    available = student_balance(student)
    if amount <= 0:
        raise ValidationError("Summa 0 dan katta bo'lishi kerak")
    if amount > available:
        raise ValidationError(f"Qaytarish mumkin bo'lgan summa: {max(0, available):,} so'm")
    r = Refund.objects.create(student=student, amount=amount, paid_at=timezone.now(), given_by=user, reason=reason)
    AuditLog.record(user, "refund", r, after={"amount": amount, "reason": reason})
    recalc_student(student)
    return r


def balances_for(student_ids) -> dict[int, int]:
    """Ko'p o'quvchi balansini 3 ta so'rovda hisoblaydi (ro'yxatlar uchun)."""
    ids = list(student_ids)
    out = dict.fromkeys(ids, 0)
    for row in (Payment.objects.filter(student_id__in=ids, cancelled_at__isnull=True)
                .values("student_id").annotate(s=Sum("amount"))):
        out[row["student_id"]] += row["s"]
    for row in Refund.objects.filter(student_id__in=ids).values("student_id").annotate(s=Sum("amount")):
        out[row["student_id"]] -= row["s"]
    for row in (Invoice.objects.filter(enrollment__student_id__in=ids).exclude(status=Invoice.Status.VOID)
                .values("enrollment__student_id").annotate(s=Sum("amount"))):
        out[row["enrollment__student_id"]] -= row["s"]
    return out


@transaction.atomic
def enroll_student(student: Student, group: Group, joined_at: date, *, user, **discount) -> Enrollment:
    """O'quvchini guruhga qo'shadi va qo'shilgan oydan joriy oygacha hisob yaratadi."""
    if group.enrollments.filter(student=student, left_at__isnull=True).exists():
        raise ValidationError("O'quvchi bu guruhda allaqachon bor")
    e = Enrollment(student=student, group=group, joined_at=joined_at, **discount)
    e.full_clean()
    e.save()
    today = timezone.localdate()
    y, m = joined_at.year, joined_at.month
    while (y, m) <= (today.year, today.month):
        upsert_invoice(e, y, m)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if student.status != Student.Status.ACTIVE:
        student.status = Student.Status.ACTIVE
        student.save(update_fields=["status"])
    AuditLog.record(user, "enroll", e, after={"group": group.pk, "joined_at": str(joined_at)})
    recalc_student(student)
    return e


@transaction.atomic
def update_discount(enrollment: Enrollment, *, user, discount_type: str, discount_value: int, reason: str = "") -> None:
    """Chegirma o'zgarsa — joriy va keyingi oylar hisoblari qayta hisoblanadi (o'tgan oylar o'zgarmaydi)."""
    before = {"type": enrollment.discount_type, "value": enrollment.discount_value}
    enrollment.discount_type, enrollment.discount_value, enrollment.discount_reason = discount_type, discount_value, reason
    enrollment.full_clean()
    enrollment.save()
    first = timezone.localdate().replace(day=1)
    for inv in enrollment.invoices.filter(period__gte=first):
        upsert_invoice(enrollment, inv.period.year, inv.period.month)
    AuditLog.record(user, "update_discount", enrollment, before=before,
                    after={"type": discount_type, "value": discount_value})
    recalc_student(enrollment.student)
