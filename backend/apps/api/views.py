from datetime import date, timedelta

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.academics.models import Attendance, Enrollment, Group, Lesson, Room, Student
from apps.academics.services import (
    AttendanceItem, cancel_lesson, generate_lessons, mark_attendance, students_of_lesson,
)
from apps.accounts.models import User
from apps.core.models import Setting
from apps.core.utils import format_sum
from apps.finance import billing
from apps.finance.models import Invoice, Payment, Refund, SalaryPayment
from apps.notifications.models import Notification

from . import serializers as s


class IsAdminRole(permissions.BasePermission):
    message = "Faqat admin uchun"

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == User.Role.ADMIN)


class Pages(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 500


def run(fn, *args, **kwargs):
    """Servis xatolarini DRF javobiga aylantiradi."""
    try:
        return fn(*args, **kwargs)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"detail": exc.messages[0] if exc.messages else str(exc)})
    except DjangoPermissionDenied as exc:
        raise serializers.ValidationError({"detail": str(exc)})


def req_date(value, name):
    d = parse_date(value or "")
    if not d:
        raise serializers.ValidationError({name: "Sana YYYY-MM-DD formatida bo'lishi kerak"})
    return d


def month_param(request) -> date:
    raw = request.query_params.get("month")
    today = timezone.localdate()
    if not raw:
        return today.replace(day=1)
    try:
        y, m = map(int, raw.split("-")[:2])
        return date(y, m, 1)
    except ValueError:
        raise serializers.ValidationError({"month": "YYYY-MM formatida bo'lishi kerak"})


class AdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminRole]


# ---------------------------------------------------------------- auth


@api_view(["GET"])
def me(request):
    return Response(s.MeSerializer(request.user).data)


# ---------------------------------------------------------------- o'qituvchi, xona


class TeacherViewSet(AdminViewSet):
    serializer_class = s.TeacherSerializer

    def get_queryset(self):
        qs = User.objects.filter(role=User.Role.TEACHER).order_by("full_name")
        if q := self.request.query_params.get("search"):
            qs = qs.filter(Q(full_name__icontains=q) | Q(phone__icontains=q))
        return qs

    def destroy(self, request, *args, **kwargs):
        teacher = self.get_object()
        if teacher.groups_taught.exists():
            # Tarix saqlanishi uchun o'chirilmaydi — faolsizlantiriladi
            teacher.is_active = False
            teacher.save(update_fields=["is_active"])
            return Response({"detail": "O'qituvchida guruhlar bor — faolsizlantirildi"})
        return super().destroy(request, *args, **kwargs)


class RoomViewSet(AdminViewSet):
    serializer_class = s.RoomSerializer
    queryset = Room.objects.order_by("name")

    def destroy(self, request, *args, **kwargs):
        if Group.objects.filter(room=self.get_object()).exists():
            raise serializers.ValidationError({"detail": "Bu xonada guruhlar bor"})
        return super().destroy(request, *args, **kwargs)


# ---------------------------------------------------------------- o'quvchi


class StudentViewSet(AdminViewSet):
    serializer_class = s.StudentSerializer

    def get_queryset(self):
        qs = Student.objects.prefetch_related(
            "parents", Prefetch("enrollments", queryset=Enrollment.objects.select_related("group"))
        ).order_by("full_name")
        p = self.request.query_params
        if q := p.get("search"):
            qs = qs.filter(Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(parents__phone__icontains=q)).distinct()
        if st := p.get("status"):
            qs = qs.filter(status=st)
        if g := p.get("group"):
            qs = qs.filter(enrollments__group_id=g, enrollments__left_at__isnull=True)
        return qs

    def list(self, request, *args, **kwargs):
        qs = list(self.filter_queryset(self.get_queryset()))
        ctx = {**self.get_serializer_context(), "balances": billing.balances_for(x.id for x in qs)}
        data = s.StudentSerializer(qs, many=True, context=ctx).data
        if request.query_params.get("debtors") == "1":
            data = [d for d in data if d["balance"] < 0]
        return Response(data)

    def destroy(self, request, *args, **kwargs):
        student = self.get_object()
        if student.enrollments.exists() or student.payments.exists():
            raise serializers.ValidationError({"detail": "O'quvchi tarixi bor — o'chirib bo'lmaydi. Guruhdan chiqaring."})
        return super().destroy(request, *args, **kwargs)

    @action(detail=True)
    def details(self, request, pk=None):
        st = self.get_object()
        enrollments = st.enrollments.select_related("group").order_by("-joined_at")
        invoices = Invoice.objects.filter(enrollment__student=st).select_related(
            "enrollment__group", "enrollment__student").order_by("-period")
        payments = st.payments.select_related("received_by", "cancelled_by", "student")
        refunds = st.refunds.select_related("given_by", "student")
        attendance = (Attendance.objects.filter(student=st).select_related("lesson__group")
                      .order_by("-lesson__date")[:60])
        return Response({
            "student": s.StudentSerializer(st).data,
            "enrollments": s.EnrollmentSerializer(enrollments, many=True).data,
            "invoices": s.InvoiceSerializer(invoices, many=True).data,
            "payments": s.PaymentSerializer(payments, many=True).data,
            "refunds": s.RefundSerializer(refunds, many=True).data,
            "attendance": [
                {"id": a.id, "date": a.lesson.date, "group_name": a.lesson.group.name, "status": a.status}
                for a in attendance
            ],
        })


# ---------------------------------------------------------------- guruh, a'zolik


class GroupViewSet(AdminViewSet):
    serializer_class = s.GroupSerializer

    def get_queryset(self):
        qs = Group.objects.select_related("teacher", "room").prefetch_related("schedule").order_by("name")
        p = self.request.query_params
        if st := p.get("status"):
            qs = qs.filter(status=st)
        if t := p.get("teacher"):
            qs = qs.filter(teacher_id=t)
        if q := p.get("search"):
            qs = qs.filter(Q(name__icontains=q) | Q(subject__icontains=q))
        return qs

    def destroy(self, request, *args, **kwargs):
        if self.get_object().enrollments.exists():
            raise serializers.ValidationError({"detail": "Guruhda o'quvchilar tarixi bor. Holatini 'Tugagan' qiling."})
        return super().destroy(request, *args, **kwargs)

    @action(detail=True)
    def students(self, request, pk=None):
        group = self.get_object()
        qs = group.enrollments.select_related("student").order_by("left_at", "student__full_name")
        if request.query_params.get("all") != "1":
            qs = qs.filter(left_at__isnull=True)
        data = s.EnrollmentSerializer(qs, many=True).data
        balances = billing.balances_for(e["student"] for e in data)
        for e in data:
            e["balance"] = balances[e["student"]]
        return Response(data)

    @action(detail=True, methods=["post"])
    def enroll(self, request, pk=None):
        group = self.get_object()
        student = get_object_or_404(Student, pk=request.data.get("student"))
        joined = req_date(request.data.get("joined_at"), "joined_at")
        e = run(billing.enroll_student, student, group, joined, user=request.user,
                discount_type=request.data.get("discount_type", "none"),
                discount_value=int(request.data.get("discount_value") or 0),
                discount_reason=request.data.get("discount_reason", ""))
        return Response(s.EnrollmentSerializer(e).data, status=status.HTTP_201_CREATED)


class EnrollmentViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = s.EnrollmentSerializer
    queryset = Enrollment.objects.select_related("student", "group")

    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        e = self.get_object()
        if e.left_at:
            raise serializers.ValidationError({"detail": "O'quvchi bu guruhdan allaqachon chiqqan"})
        left_at = req_date(request.data.get("left_at"), "left_at")
        refundable = run(billing.process_leave, e, left_at, user=request.user)
        return Response({"refundable": refundable})

    @action(detail=True, methods=["post"])
    def discount(self, request, pk=None):
        e = self.get_object()
        run(billing.update_discount, e, user=request.user,
            discount_type=request.data.get("discount_type", "none"),
            discount_value=int(request.data.get("discount_value") or 0),
            reason=request.data.get("discount_reason", ""))
        return Response(s.EnrollmentSerializer(e).data)


# ---------------------------------------------------------------- darslar, davomat


class LessonViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = s.LessonSerializer

    def get_queryset(self):
        return Lesson.objects.select_related("group__teacher", "room").order_by("date", "start_time")

    def list(self, request, *args, **kwargs):
        p = request.query_params
        start = req_date(p.get("date_from"), "date_from")
        end = req_date(p.get("date_to") or p.get("date_from"), "date_to")
        if (end - start).days > 62:
            raise serializers.ValidationError({"detail": "Oraliq 62 kundan oshmasin"})
        groups = Group.objects.filter(status=Group.Status.ACTIVE)
        if g := p.get("group"):
            groups = groups.filter(pk=g)
        for group in groups:
            generate_lessons(group, start, end)
        qs = self.get_queryset().filter(date__range=(start, end))
        if g := p.get("group"):
            qs = qs.filter(group_id=g)
        if p.get("include_cancelled") != "1":
            qs = qs.exclude(status=Lesson.Status.CANCELLED)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        lesson = self.get_object()
        start, end = parse_time(request.data.get("start_time") or ""), parse_time(request.data.get("end_time") or "")
        if not (start and end):
            raise serializers.ValidationError({"detail": "Qo'shimcha dars vaqtini kiriting"})
        makeup = run(cancel_lesson, lesson, user=request.user,
                     makeup_date=req_date(request.data.get("makeup_date"), "makeup_date"),
                     start=start, end=end, room_id=request.data.get("room") or None)
        return Response(s.LessonSerializer(makeup).data)

    @action(detail=True, methods=["get", "post"])
    def attendance(self, request, pk=None):
        lesson = self.get_object()
        if request.method == "POST":
            items = [AttendanceItem(int(i["student"]), i["status"]) for i in request.data.get("items", [])]
            run(mark_attendance, lesson, request.user, items)
        marks = {a.student_id: a for a in lesson.attendance.select_related("marked_by")}
        rows = []
        for st in sorted(students_of_lesson(lesson), key=lambda x: x.full_name):
            a = marks.get(st.id)
            rows.append({"student": st.id, "student_name": st.full_name, "status": a.status if a else None,
                         "marked_by": a.marked_by.full_name if a and a.marked_by else None,
                         "marked_at": a.marked_at if a else None})
        return Response({"lesson": s.LessonSerializer(lesson).data, "rows": rows})


# ---------------------------------------------------------------- moliya


class InvoiceViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = s.InvoiceSerializer
    pagination_class = Pages

    def get_queryset(self):
        qs = Invoice.objects.select_related("enrollment__student", "enrollment__group").order_by(
            "-period", "enrollment__student__full_name")
        p = self.request.query_params
        if p.get("month"):
            qs = qs.filter(period=month_param(self.request))
        if st := p.get("status"):
            qs = qs.filter(status__in=st.split(","))
        if g := p.get("group"):
            qs = qs.filter(enrollment__group_id=g)
        if q := p.get("search"):
            qs = qs.filter(enrollment__student__full_name__icontains=q)
        return qs

    @action(detail=False, methods=["post"])
    def generate(self, request):
        m = month_param(request)
        return Response({"count": billing.generate_month_invoices(m.year, m.month)})


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                     viewsets.GenericViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = s.PaymentSerializer
    pagination_class = Pages

    def get_queryset(self):
        qs = Payment.objects.select_related("student", "received_by", "cancelled_by")
        p = self.request.query_params
        if p.get("date_from"):
            qs = qs.filter(paid_at__date__gte=req_date(p["date_from"], "date_from"))
        if p.get("date_to"):
            qs = qs.filter(paid_at__date__lte=req_date(p["date_to"], "date_to"))
        if m := p.get("method"):
            qs = qs.filter(method=m)
        if st := p.get("student"):
            qs = qs.filter(student_id=st)
        if q := p.get("search"):
            qs = qs.filter(Q(student__full_name__icontains=q) | Q(receipt_no__icontains=q))
        return qs

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        p = run(billing.accept_payment, d["student"], d["amount"], user=request.user,
                method=d.get("method", Payment.Method.CASH), note=d.get("note", ""))
        return Response(self.get_serializer(p).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        p = run(billing.cancel_payment, self.get_object(), user=request.user, reason=request.data.get("reason", ""))
        return Response(self.get_serializer(p).data)

    @action(detail=True)
    def receipt(self, request, pk=None):
        p = self.get_object()
        groups = [e.group.name for e in p.student.enrollments.select_related("group") if e.left_at is None]
        return Response({
            **self.get_serializer(p).data,
            "center_name": Setting.get("center_name"),
            "groups": groups,
            "method_display": p.get_method_display(),
            "balance": billing.student_balance(p.student),
        })


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def public_receipt(request, token):
    """Chekdagi QR-kod shu manzilga olib keladi — chek haqiqiyligini tekshirish."""
    p = Payment.objects.filter(receipt_token=token).select_related("student").first()
    if not p:
        return Response({"valid": False}, status=404)
    name = p.student.full_name.split()
    return Response({
        "valid": not p.is_cancelled,
        "cancelled": p.is_cancelled,
        "center_name": Setting.get("center_name"),
        "receipt_no": p.receipt_no,
        "amount": p.amount,
        "amount_display": format_sum(p.amount),
        "paid_at": p.paid_at,
        # To'liq ism ko'rsatilmaydi — faqat ism va familiyaning bosh harfi
        "student": " ".join([name[0]] + [n[0] + "." for n in name[1:]]) if name else "",
    })


class RefundViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = s.RefundSerializer
    pagination_class = Pages

    def get_queryset(self):
        qs = Refund.objects.select_related("student", "given_by")
        if st := self.request.query_params.get("student"):
            qs = qs.filter(student_id=st)
        return qs

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        r = run(billing.give_refund, d["student"], d["amount"], user=request.user, reason=d["reason"])
        return Response(self.get_serializer(r).data, status=status.HTTP_201_CREATED)


class SalaryViewSet(AdminViewSet):
    serializer_class = s.SalarySerializer

    def get_queryset(self):
        qs = SalaryPayment.objects.select_related("teacher")
        p = self.request.query_params
        if p.get("month"):
            qs = qs.filter(period=month_param(self.request))
        if t := p.get("teacher"):
            qs = qs.filter(teacher_id=t)
        return qs

    def perform_create(self, ser):
        ser.save(created_by=self.request.user)


# ---------------------------------------------------------------- sozlamalar, xabarlar


class SettingsView(viewsets.ViewSet):
    permission_classes = [IsAdminRole]

    def list(self, request):
        stored = dict(Setting.objects.filter(key__in=Setting.DEFAULTS).values_list("key", "value"))
        return Response({k: stored.get(k, v) for k, v in Setting.DEFAULTS.items()})

    def create(self, request):
        for key, value in request.data.items():
            if key not in Setting.DEFAULTS:
                continue
            if key.endswith(("_day", "_days", "_min")):
                try:
                    int(value)
                except (TypeError, ValueError):
                    raise serializers.ValidationError({key: "Butun son kiriting"})
            if key.startswith("tpl_"):
                try:
                    str(value).format_map(_AnyKeys())
                except (ValueError, IndexError):
                    raise serializers.ValidationError({key: "Shablonda { } qavslar noto'g'ri"})
            Setting.objects.update_or_create(key=key, defaults={"value": str(value)})
        return self.list(request)


class _AnyKeys(dict):
    def __missing__(self, key):
        return ""


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = s.NotificationSerializer
    pagination_class = Pages

    def get_queryset(self):
        qs = Notification.objects.select_related("parent", "student")
        p = self.request.query_params
        for f in ("status", "channel", "kind"):
            if v := p.get(f):
                qs = qs.filter(**{f: v})
        return qs

    @action(detail=False)
    def eskiz_balance(self, request):
        from apps.notifications.clients import EskizClient

        try:
            return Response(EskizClient().balance().get("data", {}))
        except Exception as exc:  # noqa: BLE001 — tashqi xizmat
            return Response({"error": str(exc)[:200]}, status=502)
