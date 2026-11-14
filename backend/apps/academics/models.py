from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Student(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "O'qiyapti"
        LEFT = "left", "Ketgan"

    full_name = models.CharField("F.I.Sh.", max_length=150)
    phone = models.CharField("telefon", max_length=20, blank=True)
    birth_date = models.DateField("tug'ilgan sana", null=True, blank=True)
    note = models.TextField("izoh", blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "o'quvchi"
        verbose_name_plural = "o'quvchilar"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Parent(models.Model):
    student = models.ForeignKey(Student, related_name="parents", on_delete=models.CASCADE)
    full_name = models.CharField("F.I.Sh.", max_length=150)
    phone = models.CharField("telefon", max_length=20)
    telegram_chat_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "ota-ona"
        verbose_name_plural = "ota-onalar"

    def __str__(self):
        return f"{self.full_name} ({self.student})"

    def clean(self):
        from apps.core.utils import normalize_phone

        if not normalize_phone(self.phone):
            raise ValidationError("Telefon raqami noto'g'ri. Masalan: +998 90 123 45 67")

    def save(self, *args, **kwargs):
        from apps.core.utils import normalize_phone

        # Bot telefon raqami bo'yicha qidiradi, shuning uchun bir xil formatda saqlaymiz
        self.phone = normalize_phone(self.phone) or self.phone
        super().save(*args, **kwargs)


class Room(models.Model):
    name = models.CharField("nomi", max_length=50, unique=True)
    capacity = models.PositiveSmallIntegerField("sig'imi", default=15)

    class Meta:
        verbose_name = "xona"
        verbose_name_plural = "xonalar"

    def __str__(self):
        return self.name


class Group(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Faol"
        FINISHED = "finished", "Tugagan"

    name = models.CharField("nomi", max_length=100)
    subject = models.CharField("fan / kurs", max_length=100)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="groups_taught",
        on_delete=models.PROTECT,
        limit_choices_to={"role": "teacher"},
        verbose_name="o'qituvchi",
    )
    room = models.ForeignKey(Room, on_delete=models.PROTECT, verbose_name="xona")
    monthly_price = models.PositiveIntegerField("oylik narx (so'm)", default=300_000)
    lesson_price = models.PositiveIntegerField("bitta dars narxi (so'm)", default=25_000)
    start_date = models.DateField("boshlanish sanasi")
    end_date = models.DateField("tugash sanasi", null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        verbose_name = "guruh"
        verbose_name_plural = "guruhlar"

    def __str__(self):
        return self.name


class GroupSchedule(models.Model):
    """Haftalik jadval: masalan Du/Chor/Ju 14:00–15:30 — 3 ta qator."""

    class Weekday(models.IntegerChoices):
        MON = 0, "Dushanba"
        TUE = 1, "Seshanba"
        WED = 2, "Chorshanba"
        THU = 3, "Payshanba"
        FRI = 4, "Juma"
        SAT = 5, "Shanba"
        SUN = 6, "Yakshanba"

    group = models.ForeignKey(Group, related_name="schedule", on_delete=models.CASCADE)
    weekday = models.PositiveSmallIntegerField("hafta kuni", choices=Weekday.choices)
    start_time = models.TimeField("boshlanishi")
    end_time = models.TimeField("tugashi")

    class Meta:
        verbose_name = "jadval"
        verbose_name_plural = "jadval"
        ordering = ["weekday", "start_time"]

    def __str__(self):
        return f"{self.group} — {self.get_weekday_display()} {self.start_time:%H:%M}"

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Tugash vaqti boshlanishdan keyin bo'lishi kerak")
        if not self.group_id or self.start_time is None or self.end_time is None:
            return
        from .services import find_schedule_conflicts

        conflicts = find_schedule_conflicts(self)
        if conflicts:
            raise ValidationError("To'qnashuv: " + "; ".join(conflicts))


class Enrollment(models.Model):
    """O'quvchining guruhga a'zoligi. Chegirma shu yerda."""

    class DiscountType(models.TextChoices):
        NONE = "none", "Yo'q"
        PERCENT = "percent", "Foiz"
        FIXED = "fixed", "Qat'iy summa"

    student = models.ForeignKey(Student, related_name="enrollments", on_delete=models.PROTECT)
    group = models.ForeignKey(Group, related_name="enrollments", on_delete=models.PROTECT)
    joined_at = models.DateField("qo'shilgan sana")
    left_at = models.DateField("ketgan sana", null=True, blank=True)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices, default=DiscountType.NONE)
    discount_value = models.PositiveIntegerField("chegirma qiymati", default=0)
    discount_reason = models.CharField("chegirma sababi", max_length=200, blank=True)

    class Meta:
        verbose_name = "guruhga a'zolik"
        verbose_name_plural = "guruhga a'zoliklar"

    def __str__(self):
        return f"{self.student} → {self.group}"

    def clean(self):
        if self.left_at and self.left_at < self.joined_at:
            raise ValidationError("Ketgan sana qo'shilgan sanadan oldin bo'lishi mumkin emas")
        if self.discount_type == self.DiscountType.PERCENT and self.discount_value > 100:
            raise ValidationError("Foiz 100 dan oshmasligi kerak")


class Lesson(models.Model):
    """Aniq sanadagi dars. Jadvaldan avtomatik yaratiladi; bekor qilinsa o'rniga qo'shimcha dars."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Rejada"
        DONE = "done", "O'tildi"
        CANCELLED = "cancelled", "Bekor qilindi"

    class Kind(models.TextChoices):
        REGULAR = "regular", "Oddiy"
        MAKEUP = "makeup", "Qo'shimcha (almashtirilgan)"

    group = models.ForeignKey(Group, related_name="lessons", on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.PROTECT)
    date = models.DateField("sana")
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.REGULAR)
    replaces = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replaced_by"
    )

    class Meta:
        verbose_name = "dars"
        verbose_name_plural = "darslar"
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(fields=["group", "date", "start_time"], name="uniq_lesson_slot"),
        ]

    def __str__(self):
        return f"{self.group} {self.date} {self.start_time:%H:%M}"


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Keldi"
        ABSENT = "absent", "Kelmadi"
        EXCUSED = "excused", "Sababli"
        LATE = "late", "Kechikdi"

    lesson = models.ForeignKey(Lesson, related_name="attendance", on_delete=models.CASCADE)
    student = models.ForeignKey(Student, related_name="attendance", on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=Status.choices)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="+", null=True, on_delete=models.SET_NULL
    )
    marked_at = models.DateTimeField("belgilangan vaqt")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="+", null=True, blank=True, on_delete=models.SET_NULL
    )
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "davomat"
        verbose_name_plural = "davomat"
        constraints = [
            models.UniqueConstraint(fields=["lesson", "student"], name="uniq_attendance"),
        ]

    def __str__(self):
        return f"{self.student} — {self.lesson}: {self.get_status_display()}"
