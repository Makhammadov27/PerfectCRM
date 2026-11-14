from django.conf import settings
from django.db import models

from apps.academics.models import Lesson, Parent, Student


class AttendanceDraft(models.Model):
    """O'qituvchi botda davomat belgilayotgan paytdagi vaqtinchalik holat ("Saqlash" bosilguncha)."""

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    statuses = models.JSONField(default=dict)  # {"<student_id>": "present" | "absent" | "late" | "excused"}
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["lesson", "teacher"], name="uniq_attendance_draft")]


class Notification(models.Model):
    """Ota-onaga yuboriladigan har bir xabar. Avval navbatga qo'yiladi, keyin yuboriladi."""

    class Channel(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        SMS = "sms", "SMS"

    class Kind(models.TextChoices):
        ABSENT = "absent", "Kelmadi"
        LATE = "late", "Kechikdi"
        PAYMENT_SOON = "payment_soon", "To'lov eslatmasi"
        PAYMENT_DUE = "payment_due", "To'lov muddati bugun"
        PAYMENT_OVERDUE = "payment_overdue", "To'lov kechikdi"
        PAYMENT_RECEIVED = "payment_received", "To'lov qabul qilindi"
        OTHER = "other", "Boshqa"

    class Status(models.TextChoices):
        PENDING = "pending", "Navbatda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Xato"

    parent = models.ForeignKey(Parent, related_name="notifications", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, related_name="notifications", null=True, on_delete=models.SET_NULL)
    channel = models.CharField(max_length=10, choices=Channel.choices)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    text = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    provider_id = models.CharField(max_length=100, blank=True)
    dedupe_key = models.CharField(max_length=100, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "xabar"
        verbose_name_plural = "xabarlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_channel_display()} → {self.parent}: {self.get_kind_display()} ({self.status})"
