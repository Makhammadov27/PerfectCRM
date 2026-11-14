from django.contrib import admin

from .models import Invoice, Payment, Refund, SalaryPayment


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["enrollment", "period", "lessons_count", "amount", "paid_amount", "due_date", "status"]
    list_filter = ["status", "period"]
    search_fields = ["enrollment__student__full_name"]
    readonly_fields = [f.name for f in Invoice._meta.fields]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """To'lovlar faqat ko'rish uchun: qabul qilish va bekor qilish — API orqali (audit bilan)."""

    list_display = ["receipt_no", "student", "amount", "method", "paid_at", "cancelled_at"]
    list_filter = ["method", "paid_at"]
    search_fields = ["receipt_no", "student__full_name"]
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ["student", "amount", "paid_at", "given_by", "reason"]
    readonly_fields = [f.name for f in Refund._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SalaryPayment)
class SalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ["teacher", "period", "amount", "paid_at", "note"]
    list_filter = ["teacher", "period"]
    exclude = ["created_by"]

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
