from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import Lesson
from apps.academics.tests.factories import make_admin, make_teacher
from apps.finance.models import Invoice, Payment

NOW = timezone.make_aware(datetime(2026, 11, 16, 14, 5))  # dushanba


class ApiTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.c = APIClient()
        r = self.c.post("/api/auth/login/", {"phone": self.admin.phone, "password": "test-pass-123"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.now = patch("django.utils.timezone.now", return_value=NOW)
        self.now.start()
        self.addCleanup(self.now.stop)

    def ok(self, r, code=200):
        self.assertEqual(r.status_code, code, getattr(r, "data", r.content))
        return r.data

    def make_student(self, name="Ali Valiyev"):
        return self.ok(self.c.post("/api/students/", {
            "full_name": name, "phone": "", "parents": [{"full_name": "Ona", "phone": "+998 90 111 22 33"}],
        }, format="json"), 201)

    def make_group_api(self, **kw):
        teacher = make_teacher()
        room = self.ok(self.c.post("/api/rooms/", {"name": "101", "capacity": 12}, format="json"), 201)
        data = {"name": "Ingliz A1", "subject": "Ingliz tili", "teacher": teacher.id, "room": room["id"],
                "monthly_price": 300000, "lesson_price": 25000, "start_date": "2026-09-01",
                "schedule": [{"weekday": d, "start_time": "14:00", "end_time": "15:30"} for d in (0, 2, 4)]}
        data.update(kw)
        return self.ok(self.c.post("/api/groups/", data, format="json"), 201)

    def test_requires_auth_and_admin_role(self):
        self.assertEqual(APIClient().get("/api/students/").status_code, 401)
        t = make_teacher("+998900000055", "Ustoz")
        c = APIClient()
        tok = c.post("/api/auth/login/", {"phone": t.phone, "password": "test-pass-123"}, format="json").data
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tok['access']}")
        self.assertEqual(c.get("/api/students/").status_code, 403)

    def test_full_flow_enroll_pay_receipt_leave_refund(self):
        st = self.make_student()
        self.assertEqual(st["parents"][0]["phone"], "998901112233")
        g = self.make_group_api()
        self.ok(self.c.post(f"/api/groups/{g['id']}/enroll/", {"student": st["id"], "joined_at": "2026-11-15"},
                            format="json"), 201)
        self.assertEqual(Invoice.objects.get().amount, 175000)

        students = self.ok(self.c.get("/api/students/"))
        self.assertEqual(students[0]["balance"], -175000)
        self.assertEqual(len(self.ok(self.c.get("/api/students/?debtors=1"))), 1)

        p = self.ok(self.c.post("/api/payments/", {"student": st["id"], "amount": 175000, "method": "card"},
                                format="json"), 201)
        rc = self.ok(self.c.get(f"/api/payments/{p['id']}/receipt/"))
        self.assertEqual((rc["balance"], rc["groups"]), (0, ["Ingliz A1"]))
        pub = self.ok(APIClient().get(f"/api/public/receipt/{p['receipt_token']}/"))
        self.assertTrue(pub["valid"])
        self.assertEqual(pub["student"], "Ali V.")

        enr = self.ok(self.c.get(f"/api/groups/{g['id']}/students/"))[0]
        r = self.ok(self.c.post(f"/api/enrollments/{enr['id']}/leave/", {"left_at": "2026-11-16"}, format="json"))
        self.assertEqual(r["refundable"], 175000 - 25000)
        self.ok(self.c.post("/api/refunds/", {"student": st["id"], "amount": 150000, "reason": "Ketdi"},
                            format="json"), 201)
        self.assertEqual(self.ok(self.c.get(f"/api/students/{st['id']}/details/"))["student"]["balance"], 0)

    def test_cancel_payment_requires_reason(self):
        st = self.make_student()
        p = self.ok(self.c.post("/api/payments/", {"student": st["id"], "amount": 1000}, format="json"), 201)
        self.ok(self.c.post(f"/api/payments/{p['id']}/cancel/", {"reason": ""}, format="json"), 400)
        self.ok(self.c.post(f"/api/payments/{p['id']}/cancel/", {"reason": "Xato"}, format="json"))
        self.assertTrue(Payment.objects.get().is_cancelled)
        self.assertEqual(self.c.delete(f"/api/payments/{p['id']}/").status_code, 405)

    def test_group_schedule_conflict_returns_400(self):
        g = self.make_group_api()
        other = make_teacher("+998900000066", "Boshqa")
        r = self.c.post("/api/groups/", {
            "name": "B", "subject": "Rus", "teacher": other.id, "room": g["room"], "start_date": "2026-09-01",
            "schedule": [{"weekday": 0, "start_time": "15:00", "end_time": "16:00"}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("xonasi", str(r.data))

    def test_lessons_attendance_admin_and_cancel(self):
        st = self.make_student()
        g = self.make_group_api()
        self.c.post(f"/api/groups/{g['id']}/enroll/", {"student": st["id"], "joined_at": "2026-11-01"}, format="json")
        lessons = self.ok(self.c.get("/api/lessons/?date_from=2026-11-16&date_to=2026-11-22"))
        self.assertEqual(len(lessons), 3)
        att = self.ok(self.c.post(f"/api/lessons/{lessons[0]['id']}/attendance/",
                                  {"items": [{"student": st["id"], "status": "absent"}]}, format="json"))
        self.assertEqual(att["rows"][0]["status"], "absent")

        mk = self.ok(self.c.post(f"/api/lessons/{lessons[1]['id']}/cancel/",
                                 {"makeup_date": "2026-11-19", "start_time": "14:00", "end_time": "15:30"},
                                 format="json"))
        self.assertEqual(mk["kind"], "makeup")
        self.assertEqual(Lesson.objects.filter(status="cancelled").count(), 1)

    def test_dashboard_reports_and_exports(self):
        st = self.make_student()
        g = self.make_group_api()
        self.c.post(f"/api/groups/{g['id']}/enroll/", {"student": st["id"], "joined_at": "2026-10-01"}, format="json")
        self.c.post("/api/payments/", {"student": st["id"], "amount": 300000}, format="json")
        d = self.ok(self.c.get("/api/reports/dashboard/?month=2026-11"))
        self.assertEqual((d["income"], d["students_active"], d["total_debt"]), (300000, 1, 300000))
        self.assertEqual(len(d["income_by_day"]), 30)
        self.assertEqual(len(d["today_lessons"]), 1)
        self.assertEqual(self.ok(self.c.get("/api/reports/debtors/"))[0]["debt"], 300000)
        for kind in ("payments", "debtors", "invoices", "attendance", "salaries"):
            r = self.c.get(f"/api/reports/export/{kind}/?month=2026-11")
            self.assertEqual(r.status_code, 200, kind)
            self.assertTrue(r.content.startswith(b"PK"), kind)

    def test_settings_roundtrip_and_validation(self):
        self.assertEqual(self.ok(self.c.get("/api/settings/"))["payment_due_day"], "5")
        self.ok(self.c.post("/api/settings/", {"payment_due_day": "10", "center_name": "Bilim"}, format="json"))
        s = self.ok(self.c.get("/api/settings/"))
        self.assertEqual((s["payment_due_day"], s["center_name"]), ("10", "Bilim"))
        self.ok(self.c.post("/api/settings/", {"payment_due_day": "abc"}, format="json"), 400)
        self.ok(self.c.post("/api/settings/", {"tpl_absent": "{student"}, format="json"), 400)
        self.assertNotIn("eskiz_token", s)

    def test_teacher_create_without_password(self):
        t = self.ok(self.c.post("/api/teachers/", {"phone": "+998901234000", "full_name": "Yangi"}, format="json"), 201)
        self.assertFalse(t["telegram_linked"])
        self.assertNotIn("password", t)
