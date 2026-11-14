"""Har kuni ertalab bir marta ishga tushadi (serverda cron orqali):

    python manage.py daily_jobs

- oyning 1-kuni: shu oy hisoblarini yaratadi;
- keyingi 14 kun uchun darslarni jadvaldan yaratadi;
- to'lov eslatmalarini navbatga qo'yadi (yuborishni run_bot bajaradi).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.academics.models import Group
from apps.academics.services import generate_lessons
from apps.finance.billing import generate_month_invoices
from apps.notifications.services import send_payment_reminders


class Command(BaseCommand):
    help = "Kunlik vazifalar: oylik hisoblar, darslar, to'lov eslatmalari"

    def handle(self, *args, **opts):
        today = timezone.localdate()
        n = generate_month_invoices(today.year, today.month)  # takroriy chaqiruv xavfsiz
        self.stdout.write(f"Hisoblar: {n}")
        lessons = sum(
            generate_lessons(g, today, today + timedelta(days=14))
            for g in Group.objects.filter(status=Group.Status.ACTIVE)
        )
        self.stdout.write(f"Yangi darslar: {lessons}")
        self.stdout.write(f"Eslatmalar navbatga: {send_payment_reminders(today)}")
