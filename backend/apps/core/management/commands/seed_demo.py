"""Demo ma'lumotlar (faqat sinash uchun, alohida bazada):

    set SQLITE_NAME=demo.sqlite3
    python manage.py migrate
    python manage.py seed_demo

Admin: telefon +998900000000, parol — .env dagi DEV_ADMIN_PASSWORD.
Ota-ona va o'quvchi telefonlari ataylab yaroqsiz ("DEMO-1"), shuning uchun hech kimga SMS ketmaydi.
"""

import os
import random
from datetime import time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.academics.models import Group, GroupSchedule, Parent, Room, Student
from apps.academics.services import AttendanceItem, generate_lessons, mark_attendance, students_of_lesson
from apps.accounts.models import User
from apps.finance import billing
from apps.notifications.models import Notification

FIRST = ["Ali", "Vali", "Sardor", "Jasur", "Madina", "Dilnoza", "Aziza", "Bekzod", "Shahzod", "Nilufar", "Kamola",
         "Otabek", "Malika", "Javohir", "Sevara", "Diyor", "Zarina", "Asadbek", "Mohinur", "Islom"]
LAST = ["Karimov", "Aliyev", "Toshmatov", "Rahimov", "Yusupov", "Saidov", "Qodirov", "Ergashev", "Nazarov", "Xolmatov"]


class Command(BaseCommand):
    help = "Demo ma'lumotlar yaratadi (faqat SQLITE_NAME=demo.sqlite3 bilan)"

    def handle(self, *args, **opts):
        if "demo" not in str(settings.DATABASES["default"]["NAME"]):
            raise CommandError("Faqat demo bazada ishlaydi: SQLITE_NAME=demo.sqlite3 qilib ishga tushiring")
        password = os.getenv("DEV_ADMIN_PASSWORD")
        if not password:
            raise CommandError(".env faylida DEV_ADMIN_PASSWORD yo'q")
        random.seed(7)
        admin, _ = User.objects.get_or_create(phone="+998900000000", defaults={
            "full_name": "Admin", "role": User.Role.ADMIN, "is_staff": True, "is_superuser": True})
        admin.set_password(password)
        admin.save()
        if Group.objects.exists():
            self.stdout.write("Demo ma'lumotlar allaqachon bor")
            return

        teachers = [User.objects.create(phone=f"DEMO-T{i}", full_name=n, role=User.Role.TEACHER)
                    for i, n in enumerate(["Nodira Hasanova", "Rustam Olimov", "Gulnora Saidova"], 1)]
        rooms = [Room.objects.create(name=n, capacity=c) for n, c in [("101-xona", 14), ("102-xona", 12), ("Katta zal", 24)]]
        today = timezone.localdate()
        start = (today.replace(day=1) - timedelta(days=40)).replace(day=1)
        specs = [
            ("Ingliz tili A1", "Ingliz tili", 0, 0, (0, 2, 4), time(9), time(10, 30), 300_000, 25_000),
            ("Ingliz tili B1", "Ingliz tili", 0, 0, (0, 2, 4), time(14), time(15, 30), 360_000, 30_000),
            ("Matematika", "Matematika", 1, 1, (1, 3, 5), time(10), time(11, 30), 300_000, 25_000),
            ("IELTS 6.5", "Ingliz tili", 2, 2, (1, 3, 5), time(16), time(18), 450_000, 37_500),
            ("Rus tili", "Rus tili", 1, 1, (0, 2, 4), time(16), time(17, 30), 280_000, 23_000),
        ]
        groups = []
        for name, subj, t, r, days, st, en, mp, lp in specs:
            g = Group.objects.create(name=name, subject=subj, teacher=teachers[t], room=rooms[r], start_date=start,
                                     monthly_price=mp, lesson_price=lp)
            for d in days:
                GroupSchedule.objects.create(group=g, weekday=d, start_time=st, end_time=en)
            groups.append(g)

        n = 0
        for g in groups:
            for _ in range(random.randint(6, 10)):
                n += 1
                s = Student.objects.create(full_name=f"{random.choice(LAST)} {random.choice(FIRST)}",
                                           phone=f"DEMO-{n}")
                Parent.objects.create(student=s, full_name="Onasi", phone=f"DEMO-P{n}")
                joined = start if random.random() < 0.75 else today.replace(day=1) + timedelta(days=random.randint(3, 12))
                joined = min(joined, today)
                billing.enroll_student(s, g, joined, user=admin)

        # O'tgan oylar asosan to'langan, joriy oy — qisman
        for s in Student.objects.all():
            debt = -billing.student_balance(s)
            if debt <= 0:
                continue
            r = random.random()
            amount = debt if r < 0.55 else debt - g.monthly_price if r < 0.85 and debt > g.monthly_price else 0
            if amount > 0:
                billing.accept_payment(s, amount, user=admin, method=random.choice(["cash", "cash", "card", "transfer"]),
                                       paid_at=timezone.now() - timedelta(days=random.randint(0, 20)))

        # Davomat: o'tgan 3 hafta
        for g in groups:
            generate_lessons(g, today - timedelta(days=21), today + timedelta(days=14))
            for lesson in g.lessons.filter(date__lt=today):
                items = [AttendanceItem(st.id, random.choices(["present", "absent", "late", "excused"], [80, 8, 8, 4])[0])
                         for st in students_of_lesson(lesson)]
                mark_attendance(lesson, admin, items)
        Notification.objects.all().delete()  # demo xabarlar yuborilmasin (raqamlar baribir yaroqsiz)
        self.stdout.write(self.style.SUCCESS(f"Tayyor: {Student.objects.count()} o'quvchi, {len(groups)} guruh"))
