from datetime import date, datetime, time

from django.test import TestCase
from django.utils import timezone

from apps.academics.models import Lesson, Parent
from apps.academics.services import AttendanceItem, generate_lessons, mark_attendance
from apps.academics.tests.factories import enroll, make_admin, make_group
from apps.core.utils import normalize_phone
from apps.finance import billing
from apps.notifications.bot import BTN_PAYMENT, ParentBot
from apps.notifications.clients import SendError
from apps.notifications.models import Notification
from apps.notifications.services import send_payment_reminders, send_pending


class FakeSms:
    def __init__(self, fail=None):
        self.sent, self.fail = [], fail

    def send_sms(self, phone, text):
        if self.fail:
            raise self.fail
        self.sent.append((phone, text))
        return "sms-1"


class FakeTelegram:
    def __init__(self, fail=None):
        self.sent, self.fail = [], fail

    def send_message(self, chat_id, text, **extra):
        if self.fail:
            raise self.fail
        self.sent.append((chat_id, text, extra))
        return "1"


class PhoneTests(TestCase):
    def test_normalize(self):
        for raw in ["+998 90 123-45-67", "998901234567", "90 123 45 67", "(90) 1234567"]:
            self.assertEqual(normalize_phone(raw), "998901234567")
        self.assertEqual(normalize_phone("12345"), "")


class BaseCase(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.group = make_group()
        self.e = enroll(self.group, date(2026, 10, 1))
        self.student = self.e.student
        self.parent = Parent.objects.create(student=self.student, full_name="Ona", phone="+998 90 123 45 67")


class RoutingTests(BaseCase):
    def test_parent_phone_saved_normalized(self):
        self.assertEqual(self.parent.phone, "998901234567")

    def test_absent_goes_to_sms_when_no_telegram(self):
        generate_lessons(self.group, date(2026, 11, 2), date(2026, 11, 2))
        lesson = Lesson.objects.get()
        t = timezone.make_aware(datetime.combine(lesson.date, time(14, 5)))
        mark_attendance(lesson, self.group.teacher, [AttendanceItem(self.student.id, "absent")], marked_at=t, now=t)
        n = Notification.objects.get()
        self.assertEqual((n.channel, n.kind), ("sms", "absent"))
        self.assertIn("02.11.2026", n.text)

        sms = FakeSms()
        send_pending(sms=sms, tg=FakeTelegram())
        n.refresh_from_db()
        self.assertEqual(n.status, "sent")
        self.assertEqual(sms.sent[0][0], "998901234567")

    def test_present_sends_nothing(self):
        generate_lessons(self.group, date(2026, 11, 2), date(2026, 11, 2))
        lesson = Lesson.objects.get()
        t = timezone.make_aware(datetime.combine(lesson.date, time(14, 5)))
        mark_attendance(lesson, self.group.teacher, [AttendanceItem(self.student.id, "present")], marked_at=t, now=t)
        self.assertFalse(Notification.objects.exists())

    def test_telegram_preferred_and_blocked_bot_falls_back_to_sms(self):
        self.parent.telegram_chat_id = 555
        self.parent.save()
        billing.accept_payment(self.student, 300_000, user=self.admin)
        n = Notification.objects.get()
        self.assertEqual((n.channel, n.kind), ("telegram", "payment_received"))

        sms = FakeSms()
        send_pending(sms=sms, tg=FakeTelegram(fail=SendError("blocked", permanent=True)))
        n.refresh_from_db()
        self.assertEqual(n.status, "failed")
        self.parent.refresh_from_db()
        self.assertIsNone(self.parent.telegram_chat_id)
        send_pending(sms=sms, tg=FakeTelegram())
        self.assertEqual(len(sms.sent), 1)
        self.assertIn("300 000 so'm", sms.sent[0][1])

    def test_temporary_error_retried(self):
        billing.accept_payment(self.student, 100_000, user=self.admin)
        send_pending(sms=FakeSms(fail=SendError("timeout")), tg=FakeTelegram())
        n = Notification.objects.get()
        self.assertEqual((n.status, n.attempts), ("pending", 1))


class ReminderTests(BaseCase):
    def setUp(self):
        super().setUp()
        billing.generate_month_invoices(2026, 11)  # muddat 05.11

    def kinds(self):
        return list(Notification.objects.values_list("kind", flat=True))

    def test_three_days_before(self):
        self.assertEqual(send_payment_reminders(date(2026, 11, 2)), 1)
        self.assertEqual(self.kinds(), ["payment_soon"])

    def test_due_day_and_no_duplicates(self):
        send_payment_reminders(date(2026, 11, 5))
        send_payment_reminders(date(2026, 11, 5))
        self.assertEqual(self.kinds(), ["payment_due"])

    def test_overdue_every_3_days(self):
        self.assertEqual(send_payment_reminders(date(2026, 11, 7)), 0)
        self.assertEqual(send_payment_reminders(date(2026, 11, 8)), 1)

    def test_paid_invoice_no_reminder(self):
        billing.accept_payment(self.student, 300_000, user=self.admin)
        Notification.objects.all().delete()
        self.assertEqual(send_payment_reminders(date(2026, 11, 5)), 0)


class BotTests(BaseCase):
    def msg(self, **kw):
        base = {"chat": {"id": 777, "type": "private"}, "from": {"id": 42}}
        base.update(kw)
        return {"update_id": 1, "message": base}

    def test_start_asks_for_contact(self):
        api = FakeTelegram()
        ParentBot(api).handle_update(self.msg(text="/start"))
        self.assertTrue(api.sent[0][2]["reply_markup"]["keyboard"][0][0]["request_contact"])

    def test_contact_links_parent(self):
        api = FakeTelegram()
        ParentBot(api).handle_update(self.msg(contact={"phone_number": "+998901234567", "user_id": 42}))
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.telegram_chat_id, 777)
        self.assertIn(self.student.full_name, api.sent[0][1])

    def test_someone_elses_contact_rejected(self):
        ParentBot(FakeTelegram()).handle_update(self.msg(contact={"phone_number": "998901234567", "user_id": 99}))
        self.parent.refresh_from_db()
        self.assertIsNone(self.parent.telegram_chat_id)

    def test_unknown_phone(self):
        api = FakeTelegram()
        ParentBot(api).handle_update(self.msg(contact={"phone_number": "998911111111", "user_id": 42}))
        self.assertIn("topilmadi", api.sent[0][1])

    def test_payment_button_shows_debt(self):
        self.parent.telegram_chat_id = 777
        self.parent.save()
        billing.generate_month_invoices(2026, 11)
        api = FakeTelegram()
        ParentBot(api).handle_update(self.msg(text=BTN_PAYMENT))
        self.assertIn("300 000 so'm", api.sent[0][1])
