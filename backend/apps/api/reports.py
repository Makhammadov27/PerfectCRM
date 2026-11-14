"""Hisobotlar va Excel eksport."""

from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.academics.models import Attendance, Group, Lesson, Student
from apps.academics.services import generate_lessons, month_bounds
from apps.accounts.models import User
from apps.finance.models import Invoice, Payment, Refund, SalaryPayment

from .views import IsAdminRole, month_param

STATUS_UZ = {"present": "Keldi", "absent": "Kelmadi", "late": "Kechikdi", "excused": "Sababli"}
METHOD_UZ = dict(Payment.Method.choices)
INVOICE_UZ = dict(Invoice.Status.choices)


def _month_payments(first: date, last: date):
    return Payment.objects.filter(paid_at__date__range=(first, last), cancelled_at__isnull=True)


def debtors_rows(today: date | None = None) -> list[dict]:
    today = today or timezone.localdate()
    open_inv = (Invoice.objects.filter(status__in=[Invoice.Status.OPEN, Invoice.Status.PARTIAL])
                .select_related("enrollment__student", "enrollment__group"))
    per_student: dict[int, dict] = {}
    for inv in open_inv:
        st = inv.enrollment.student
        row = per_student.setdefault(st.id, {
            "student_id": st.id, "student_name": st.full_name, "phone": st.phone,
            "parent_phones": [p.phone for p in st.parents.all()], "groups": set(), "debt": 0,
            "oldest_due": inv.due_date, "overdue_debt": 0,
        })
        row["groups"].add(inv.enrollment.group.name)
        row["debt"] += inv.debt
        row["oldest_due"] = min(row["oldest_due"], inv.due_date)
        if inv.due_date < today:
            row["overdue_debt"] += inv.debt
    rows = []
    for r in per_student.values():
        r["groups"] = sorted(r["groups"])
        r["days_overdue"] = max(0, (today - r["oldest_due"]).days)
        rows.append(r)
    return sorted(rows, key=lambda r: (-r["days_overdue"], -r["debt"]))


def attendance_rows(first: date, last: date) -> list[dict]:
    qs = (Attendance.objects.filter(lesson__date__range=(first, last))
          .values("lesson__group_id", "lesson__group__name", "lesson__group__teacher__full_name")
          .annotate(total=Count("id"),
                    present=Count("id", filter=Q(status="present")),
                    late=Count("id", filter=Q(status="late")),
                    absent=Count("id", filter=Q(status="absent")),
                    excused=Count("id", filter=Q(status="excused"))))
    lessons = dict(Lesson.objects.filter(date__range=(first, last), status=Lesson.Status.DONE)
                   .values_list("group_id").annotate(c=Count("id")))
    rows = []
    for r in qs:
        came = r["present"] + r["late"]
        rows.append({
            "group_id": r["lesson__group_id"], "group_name": r["lesson__group__name"],
            "teacher_name": r["lesson__group__teacher__full_name"], "lessons": lessons.get(r["lesson__group_id"], 0),
            "present": r["present"], "late": r["late"], "absent": r["absent"], "excused": r["excused"],
            "rate": round(came * 100 / r["total"]) if r["total"] else 0,
        })
    return sorted(rows, key=lambda r: r["group_name"])


@api_view(["GET"])
@permission_classes([IsAdminRole])
def dashboard(request):
    m = month_param(request)
    first, last = month_bounds(m.year, m.month)
    today = timezone.localdate()

    payments = _month_payments(first, last)
    income = payments.aggregate(s=Sum("amount"))["s"] or 0
    refunds = Refund.objects.filter(paid_at__date__range=(first, last)).aggregate(s=Sum("amount"))["s"] or 0
    salaries = SalaryPayment.objects.filter(period=first, paid_at__isnull=False).aggregate(s=Sum("amount"))["s"] or 0
    inv = Invoice.objects.filter(period=first).exclude(status=Invoice.Status.VOID).aggregate(
        expected=Sum("amount"), collected=Sum("paid_amount"))

    by_day = defaultdict(int)
    for paid_at, amount in payments.values_list("paid_at", "amount"):
        by_day[timezone.localtime(paid_at).date()] += amount
    days = [{"date": first + timedelta(days=i), "amount": by_day.get(first + timedelta(days=i), 0)}
            for i in range((last - first).days + 1)]
    by_method = [{"method": r["method"], "label": METHOD_UZ[r["method"]], "amount": r["s"]}
                 for r in payments.values("method").annotate(s=Sum("amount")).order_by("-s")]

    att = Attendance.objects.filter(lesson__date__range=(first, last)).aggregate(
        total=Count("id"), came=Count("id", filter=Q(status__in=["present", "late"])))
    debtors = debtors_rows(today)

    for g in Group.objects.filter(status=Group.Status.ACTIVE):
        generate_lessons(g, today, today)
    todays = (Lesson.objects.filter(date=today).exclude(status=Lesson.Status.CANCELLED)
              .select_related("group__teacher", "room").annotate(marks=Count("attendance")).order_by("start_time"))

    return Response({
        "month": first,
        "students_active": Student.objects.filter(status=Student.Status.ACTIVE).count(),
        "groups_active": Group.objects.filter(status=Group.Status.ACTIVE).count(),
        "teachers_active": User.objects.filter(role=User.Role.TEACHER, is_active=True).count(),
        "income": income,
        "refunds": refunds,
        "salaries": salaries,
        "net": income - refunds - salaries,
        "expected": inv["expected"] or 0,
        "collected": inv["collected"] or 0,
        "total_debt": sum(r["debt"] for r in debtors),
        "overdue_debt": sum(r["overdue_debt"] for r in debtors),
        "debtors_count": sum(1 for r in debtors if r["overdue_debt"] > 0),
        "attendance_rate": round(att["came"] * 100 / att["total"]) if att["total"] else None,
        "income_by_day": days,
        "income_by_method": by_method,
        "today_lessons": [{
            "id": l.id, "group_name": l.group.name, "teacher_name": l.group.teacher.full_name,
            "room_name": l.room.name, "start_time": l.start_time, "end_time": l.end_time,
            "attendance_taken": l.marks > 0, "kind": l.kind,
        } for l in todays],
    })


@api_view(["GET"])
@permission_classes([IsAdminRole])
def debtors(request):
    return Response(debtors_rows())


@api_view(["GET"])
@permission_classes([IsAdminRole])
def attendance_report(request):
    m = month_param(request)
    return Response(attendance_rows(*month_bounds(m.year, m.month)))


# ---------------------------------------------------------------- Excel


def _xlsx(title: str, headers: list[str], rows: list[list], filename: str, money_cols=()) -> HttpResponse:
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.append(headers)
    head_fill = PatternFill("solid", fgColor="4F46E5")
    for c in ws[1]:
        c.font, c.fill, c.alignment = Font(bold=True, color="FFFFFF"), head_fill, Alignment(vertical="center")
    for r in rows:
        ws.append(r)
    for idx in money_cols:
        for cell in ws.iter_cols(min_col=idx, max_col=idx, min_row=2):
            for c in cell:
                c.number_format = "# ##0"
    for i, h in enumerate(headers, 1):
        width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows if r[i - 1] is not None] or [10])
        ws.column_dimensions[get_column_letter(i)].width = min(45, width + 3)
    ws.freeze_panes = "A2"
    buf = BytesIO()
    wb.save(buf)
    resp = HttpResponse(buf.getvalue(),
                        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@api_view(["GET"])
@permission_classes([IsAdminRole])
def export(request, kind):
    m = month_param(request)
    first, last = month_bounds(m.year, m.month)
    tag = f"{first:%Y-%m}"
    if kind == "payments":
        qs = (Payment.objects.filter(paid_at__date__range=(first, last))
              .select_related("student", "received_by").order_by("paid_at"))
        rows = [[p.receipt_no, timezone.localtime(p.paid_at).strftime("%d.%m.%Y %H:%M"), p.student.full_name,
                 p.amount, METHOD_UZ[p.method], p.received_by.full_name,
                 "Bekor qilingan: " + p.cancel_reason if p.is_cancelled else "", p.note] for p in qs]
        return _xlsx("To'lovlar", ["Chek", "Sana", "O'quvchi", "Summa", "Usul", "Qabul qildi", "Holat", "Izoh"],
                     rows, f"tolovlar-{tag}.xlsx", money_cols=[4])
    if kind == "debtors":
        rows = [[r["student_name"], ", ".join(r["parent_phones"]), ", ".join(r["groups"]), r["debt"],
                 r["overdue_debt"], r["oldest_due"].strftime("%d.%m.%Y"), r["days_overdue"]] for r in debtors_rows()]
        return _xlsx("Qarzdorlar", ["O'quvchi", "Ota-ona tel.", "Guruhlar", "Jami qarz",
                                    "Muddati o'tgan", "Eng eski muddat", "Kechikish (kun)"],
                     rows, f"qarzdorlar-{timezone.localdate():%Y-%m-%d}.xlsx", money_cols=[4, 5])
    if kind == "invoices":
        qs = (Invoice.objects.filter(period=first).exclude(status=Invoice.Status.VOID)
              .select_related("enrollment__student", "enrollment__group").order_by("enrollment__group__name"))
        rows = [[i.enrollment.student.full_name, i.enrollment.group.name, i.lessons_count, i.base_amount,
                 i.discount_amount, i.amount, i.paid_amount, i.debt, i.due_date.strftime("%d.%m.%Y"),
                 INVOICE_UZ[i.status]] for i in qs]
        return _xlsx("Hisoblar", ["O'quvchi", "Guruh", "Darslar", "Narx", "Chegirma", "To'lanishi kerak",
                                  "To'langan", "Qarz", "Muddat", "Holat"],
                     rows, f"hisoblar-{tag}.xlsx", money_cols=[4, 5, 6, 7, 8])
    if kind == "attendance":
        qs = (Attendance.objects.filter(lesson__date__range=(first, last))
              .select_related("lesson__group", "student").order_by("lesson__group__name", "lesson__date",
                                                                   "student__full_name"))
        rows = [[a.lesson.group.name, a.lesson.date.strftime("%d.%m.%Y"), a.student.full_name,
                 STATUS_UZ[a.status]] for a in qs]
        return _xlsx("Davomat", ["Guruh", "Sana", "O'quvchi", "Holat"], rows, f"davomat-{tag}.xlsx")
    if kind == "salaries":
        qs = SalaryPayment.objects.filter(period=first).select_related("teacher")
        rows = [[x.teacher.full_name, x.amount, x.paid_at.strftime("%d.%m.%Y") if x.paid_at else "To'lanmagan",
                 x.note] for x in qs]
        return _xlsx("Maoshlar", ["O'qituvchi", "Summa", "To'langan", "Izoh"], rows, f"maoshlar-{tag}.xlsx",
                     money_cols=[2])
    return Response({"detail": "Noma'lum hisobot"}, status=404)
