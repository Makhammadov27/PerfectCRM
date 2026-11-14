import uuid

from django.conf import settings
from django.db import models

from apps.academics.models import Enrollment, Student


class Invoice(models.Model):
    """O'quvchining bitta guruh bo'yicha bir oylik hisobi."""

    class Status(models.TextChoices):
        OPEN = "open", "To'lanmagan"
        PARTIAL = "partial", "Qisman to'langan"
        PAID = "paid", "To'langan"
        VOID = "void", "Bekor qilingan"

    enrollment = models.ForeignKey(Enrollment, related_name="invoices", on_delete=models.PROTECT)
    period = models.DateField("oy (1-kun)")
    lessons_count = models.PositiveSmallIntegerField("darslar soni")
    base_amount = models.PositiveIntegerField("chegirmasiz summa")
    discount_amount = models.PositiveIntegerField("chegirma", default=0)
    amount = models.PositiveIntegerField("to'lanishi kerak")
    paid_amount = models.PositiveIntegerField("to'langan", default=0)
    due_date = models.DateField("to'lov muddati")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "oylik hisob"
        verbose_name_plural = "oylik hisoblar"
        ordering = ["period", "id"]
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "period"], name="uniq_invoice_period"),
        ]

    def __str__(self):
        return f"{self.enrollment} {self.period:%Y-%m}: {self.amount:,}"

    @property
    def debt(self):
        return 0 if self.status == self.Status.VOID else self.amount - self.paid_amount


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Naqd"
        CARD = "card", "Karta"
        TRANSFER = "transfer", "O'tkazma"

    student = models.ForeignKey(Student, related_name="payments", on_delete=models.PROTECT)
    amount = models.PositiveIntegerField("summa")
    method = models.CharField("usul", max_length=10, choices=Method.choices, default=Method.CASH)
    paid_at = models.DateTimeField("to'langan vaqt")
    receipt_no = models.CharField("chek raqami", max_length=20, unique=True)
    receipt_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    note = models.CharField("izoh", max_length=200, blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="+", on_delete=models.PROTECT)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="+", null=True, blank=True, on_delete=models.PROTECT
    )
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "to'lov"
        verbose_name_plural = "to'lovlar"
        ordering = ["-paid_at"]

    def __str__(self):
        return f"#{self.receipt_no} {self.student} {self.amount:,}"

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None


class Refund(models.Model):
    """O'quvchiga qaytarilgan pul (masalan, oy o'rtasida ketganda)."""

    student = models.ForeignKey(Student, related_name="refunds", on_delete=models.PROTECT)
    amount = models.PositiveIntegerField("summa")
    paid_at = models.DateTimeField("berilgan vaqt")
    given_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="+", on_delete=models.PROTECT)
    reason = models.CharField("sabab", max_length=200)

    class Meta:
        verbose_name = "qaytarilgan pul"
        verbose_name_plural = "qaytarilgan pullar"
        ordering = ["-paid_at"]

    def __str__(self):
        return f"{self.student} −{self.amount:,}"


class SalaryPayment(models.Model):
    """O'qituvchi maoshi — admin summani qo'lda kiritadi va 'to'landi' deb belgilaydi."""

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="salaries", on_delete=models.PROTECT,
        limit_choices_to={"role": "teacher"},
    )
    period = models.DateField("oy (1-kun)")
    amount = models.PositiveIntegerField("summa")
    paid_at = models.DateField("to'langan sana", null=True, blank=True)
    note = models.CharField("izoh", max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="+", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "maosh"
        verbose_name_plural = "maoshlar"
        ordering = ["-period"]

    def __str__(self):
        return f"{self.teacher} {self.period:%Y-%m}: {self.amount:,}"

    @property
    def is_paid(self):
        return self.paid_at is not None
