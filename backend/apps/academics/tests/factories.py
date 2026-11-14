"""Testlar uchun tayyor ma'lumotlar."""

from datetime import date, time

from apps.accounts.models import User
from apps.academics.models import Enrollment, Group, GroupSchedule, Room, Student

MWF = (0, 2, 4)  # Du / Chor / Ju


def make_admin(phone="+998900000001"):
    return User.objects.create_user(phone, "test-pass-123", full_name="Admin", role=User.Role.ADMIN)


def make_teacher(phone="+998900000002", name="Ustoz"):
    return User.objects.create_user(phone, "test-pass-123", full_name=name, role=User.Role.TEACHER)


def make_group(teacher=None, room=None, weekdays=MWF, start=time(14, 0), end=time(15, 30),
               start_date=date(2026, 9, 1), name="Ingliz tili A1"):
    teacher = teacher or make_teacher()
    room = room or Room.objects.create(name=f"Xona {Room.objects.count() + 1}")
    g = Group.objects.create(name=name, subject="Ingliz tili", teacher=teacher, room=room, start_date=start_date)
    for wd in weekdays:
        GroupSchedule.objects.create(group=g, weekday=wd, start_time=start, end_time=end)
    return g


def enroll(group, joined_at, name="Ali Valiyev", **kw):
    s = Student.objects.create(full_name=name)
    return Enrollment.objects.create(student=s, group=group, joined_at=joined_at, **kw)
