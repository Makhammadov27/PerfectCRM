from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.academics.models import Enrollment, Group, GroupSchedule, Lesson, Parent, Room, Student
from apps.accounts.models import User
from apps.finance.models import Invoice, Payment, Refund, SalaryPayment
from apps.notifications.models import Notification


def as_drf_error(exc: DjangoValidationError) -> serializers.ValidationError:
    return serializers.ValidationError(exc.messages)


# ---------------------------------------------------------------- foydalanuvchilar


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone", "full_name", "role"]


class TeacherSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    telegram_linked = serializers.SerializerMethodField()
    groups_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "phone", "full_name", "is_active", "password", "telegram_linked", "groups_count"]

    def get_telegram_linked(self, obj):
        return obj.telegram_chat_id is not None

    def get_groups_count(self, obj):
        return obj.groups_taught.filter(status=Group.Status.ACTIVE).count()

    def create(self, data):
        password = data.pop("password", "") or None
        user = User(role=User.Role.TEACHER, **data)
        # O'qituvchi botdan foydalanadi; parol berilmasa veb-panelga kira olmaydi
        user.set_password(password) if password else user.set_unusable_password()
        user.save()
        return user

    def update(self, user, data):
        password = data.pop("password", "")
        for k, v in data.items():
            setattr(user, k, v)
        if password:
            user.set_password(password)
        user.save()
        return user


# ---------------------------------------------------------------- akademik


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "name", "capacity"]


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupSchedule
        fields = ["weekday", "start_time", "end_time"]


class GroupSerializer(serializers.ModelSerializer):
    schedule = ScheduleSerializer(many=True)
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    room_name = serializers.CharField(source="room.name", read_only=True)
    students_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "name", "subject", "teacher", "teacher_name", "room", "room_name", "monthly_price",
                  "lesson_price", "start_date", "end_date", "status", "schedule", "students_count"]

    def get_students_count(self, obj):
        return obj.enrollments.filter(left_at__isnull=True).count()

    def validate_teacher(self, teacher):
        if teacher.role != User.Role.TEACHER:
            raise serializers.ValidationError("O'qituvchini tanlang")
        return teacher

    def validate_schedule(self, value):
        if not value:
            raise serializers.ValidationError("Kamida bitta dars kunini kiriting")
        return value

    def _save_schedule(self, group, slots):
        group.schedule.all().delete()
        for s in slots:
            slot = GroupSchedule(group=group, **s)
            try:
                slot.full_clean()
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"schedule": exc.messages})
            slot.save()
        # Kelajakdagi, hali davomat olinmagan darslar yangi jadvalga moslanadi
        from django.utils import timezone

        today = timezone.localdate()
        group.lessons.filter(date__gte=today, status=Lesson.Status.PLANNED, kind=Lesson.Kind.REGULAR,
                             attendance__isnull=True).delete()

    @transaction.atomic
    def create(self, data):
        slots = data.pop("schedule")
        group = Group.objects.create(**data)
        self._save_schedule(group, slots)
        return group

    @transaction.atomic
    def update(self, group, data):
        slots = data.pop("schedule", None)
        for k, v in data.items():
            setattr(group, k, v)
        group.save()
        if slots is not None:
            self._save_schedule(group, slots)
        return group


class ParentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    telegram_linked = serializers.SerializerMethodField()

    class Meta:
        model = Parent
        fields = ["id", "full_name", "phone", "telegram_linked"]

    def get_telegram_linked(self, obj):
        return obj.telegram_chat_id is not None

    def validate_phone(self, value):
        from apps.core.utils import normalize_phone

        if not normalize_phone(value):
            raise serializers.ValidationError("Telefon raqami noto'g'ri. Masalan: +998 90 123 45 67")
        return value


class StudentSerializer(serializers.ModelSerializer):
    parents = ParentSerializer(many=True, required=False)
    groups = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ["id", "full_name", "phone", "birth_date", "note", "status", "created_at", "parents", "groups",
                  "balance"]
        read_only_fields = ["status", "created_at"]

    def get_groups(self, obj):
        return [{"id": e.group_id, "name": e.group.name, "enrollment_id": e.id}
                for e in obj.enrollments.all() if e.left_at is None]

    def get_balance(self, obj):
        balances = self.context.get("balances")
        if balances is not None and obj.id in balances:
            return balances[obj.id]
        from apps.finance.billing import student_balance

        return student_balance(obj)

    def _save_parents(self, student, parents):
        keep = []
        for p in parents:
            pid = p.pop("id", None)
            obj = student.parents.filter(pk=pid).first() if pid else None
            if obj is None:
                obj = Parent(student=student)
            for k, v in p.items():
                setattr(obj, k, v)
            obj.save()
            keep.append(obj.pk)
        student.parents.exclude(pk__in=keep).delete()

    @transaction.atomic
    def create(self, data):
        parents = data.pop("parents", [])
        student = Student.objects.create(**data)
        self._save_parents(student, parents)
        return student

    @transaction.atomic
    def update(self, student, data):
        parents = data.pop("parents", None)
        for k, v in data.items():
            setattr(student, k, v)
        student.save()
        if parents is not None:
            self._save_parents(student, parents)
        return student


class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    student_phone = serializers.CharField(source="student.phone", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = Enrollment
        fields = ["id", "student", "student_name", "student_phone", "group", "group_name", "joined_at", "left_at",
                  "discount_type", "discount_value", "discount_reason"]
        read_only_fields = ["left_at"]


class LessonSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    teacher_name = serializers.CharField(source="group.teacher.full_name", read_only=True)
    room_name = serializers.CharField(source="room.name", read_only=True)
    attendance_taken = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ["id", "group", "group_name", "teacher_name", "room", "room_name", "date", "start_time",
                  "end_time", "status", "kind", "replaces", "attendance_taken"]

    def get_attendance_taken(self, obj):
        return obj.attendance.exists()


# ---------------------------------------------------------------- moliya


class InvoiceSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(source="enrollment.student_id", read_only=True)
    student_name = serializers.CharField(source="enrollment.student.full_name", read_only=True)
    group_name = serializers.CharField(source="enrollment.group.name", read_only=True)
    debt = serializers.IntegerField(read_only=True)

    class Meta:
        model = Invoice
        fields = ["id", "student_id", "student_name", "group_name", "period", "lessons_count", "base_amount",
                  "discount_amount", "amount", "paid_amount", "debt", "due_date", "status"]


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    received_by_name = serializers.CharField(source="received_by.full_name", read_only=True)
    cancelled_by_name = serializers.CharField(source="cancelled_by.full_name", read_only=True, default=None)

    class Meta:
        model = Payment
        fields = ["id", "student", "student_name", "amount", "method", "paid_at", "receipt_no", "receipt_token",
                  "note", "received_by_name", "cancelled_at", "cancelled_by_name", "cancel_reason"]
        read_only_fields = ["paid_at", "receipt_no", "receipt_token", "cancelled_at", "cancel_reason"]


class RefundSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    given_by_name = serializers.CharField(source="given_by.full_name", read_only=True)

    class Meta:
        model = Refund
        fields = ["id", "student", "student_name", "amount", "paid_at", "given_by_name", "reason"]
        read_only_fields = ["paid_at"]


class SalarySerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)

    class Meta:
        model = SalaryPayment
        fields = ["id", "teacher", "teacher_name", "period", "amount", "paid_at", "note"]

    def validate_period(self, value):
        return value.replace(day=1)


class NotificationSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.full_name", read_only=True)
    parent_phone = serializers.CharField(source="parent.phone", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = ["id", "parent_name", "parent_phone", "student_name", "channel", "kind", "text", "status",
                  "attempts", "error", "created_at", "sent_at"]
