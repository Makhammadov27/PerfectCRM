from django.conf import settings
from django.db import models


class Setting(models.Model):
    """Admin o'zgartira oladigan sozlamalar (to'lov muddati kuni, davomat oynasi va h.k.)."""

    DEFAULTS = {
        "payment_due_day": "5",  # har oyning shu kunigacha to'lanadi
        "first_invoice_due_days": "5",  # yangi o'quvchi: qo'shilgan kundan + N kun
        "attendance_open_before_min": "15",  # dars boshlanishidan N daqiqa oldin ochiladi
        "attendance_close_after_min": "120",  # dars tugaganidan N daqiqa keyin yopiladi
        "center_name": "O'quv markaz",
        "reminder_days_before": "3",  # muddatdan N kun oldin eslatma
        "overdue_repeat_days": "3",  # kechikkan bo'lsa har N kunda eslatma
        # Xabar shablonlari. Eskiz.uz SMS matnlarini moderatsiyadan o'tkazishni talab qiladi —
        # shablon o'zgarsa, Eskiz kabinetida ham yangi matnni tasdiqlatish kerak.
        "tpl_absent": "{center}: {student} bugun ({date}) {group} darsiga kelmadi.",
        "tpl_late": "{center}: {student} bugun ({date}) {group} darsiga kechikdi.",
        "tpl_payment_soon": "{center}: {student} uchun {month} oyi to'lovi {amount}. Muddat: {due}.",
        "tpl_payment_due": "{center}: {student} uchun {month} oyi to'lovi bugun ({due}) muddati tugaydi. Qarz: {debt}.",
        "tpl_payment_overdue": "{center}: {student} uchun {month} oyi to'lovi kechikdi. Qarz: {debt}.",
        "tpl_payment_received": "{center}: {student} uchun {amount} qabul qilindi. Chek: {receipt}. Balans: {balance}.",
    }

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()

    class Meta:
        verbose_name = "sozlama"
        verbose_name_plural = "sozlamalar"

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get(cls, key: str) -> str:
        row = cls.objects.filter(key=key).first()
        return row.value if row else cls.DEFAULTS[key]

    @classmethod
    def get_int(cls, key: str) -> int:
        return int(cls.get(key))


class AuditLog(models.Model):
    """Kim, qachon, nimani o'zgartirdi. Pul va davomat o'zgarishlari shu yerga yoziladi."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=50)
    entity = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=50)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "audit yozuvi"
        verbose_name_plural = "audit log"
        ordering = ["-at"]

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.user} {self.action} {self.entity}#{self.entity_id}"

    @classmethod
    def record(cls, user, action, obj, before=None, after=None):
        return cls.objects.create(
            user=user if getattr(user, "pk", None) else None,
            action=action,
            entity=obj._meta.model_name,
            entity_id=str(obj.pk),
            before=before,
            after=after,
        )
