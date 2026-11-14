from datetime import date, datetime, time
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.academics.models import Attendance, Lesson, Parent
from apps.academics.tests.factories import enroll, make_group, make_teacher
from apps.notifications.bot import CenterBot
from apps.notifications.clients import SendError
from apps.notifications.models import AttendanceDraft, Notification
from apps.notifications.teacher_bot import BTN_TAKE_ATTENDANCE

MONDAY = date(2026, 11, 2)


def tashkent(d, hh, mm=0):
    return timezone.make_aware(datetime.combine(d, time(hh, mm)))


class FakeApi:
    def __init__(self):
        self.sent, self.calls = [], []

    def send_message(self, chat_id, text, **extra):
        self.sent.append((chat_id, text, extra))
        return "1"

    def call(self, method, **params):
        self.calls.append((method, params))
        return {}

    def last(self, method):
        return [p for m, p in self.calls if m == method][-1]


class TeacherBotTests(TestCase):
    TEACHER_CHAT = 1001

    def setUp(self):
        self.group = make_group()  # Du/Chor/Ju 14:00–15:30
        self.teacher = self.group.teacher
        self.teacher.telegram_chat_id = self.TEACHER_CHAT
        self.teacher.save()
        self.ali = enroll(self.group, date(2026, 10, 1), name="Ali").student
        self.vali = enroll(self.group, date(2026, 10, 1), name="Vali").student
        Parent.objects.create(student=self.vali, full_name="Vali onasi", phone="901112233")
        self.api = FakeApi()
        self.bot = CenterBot(self.api)
        self.now = patch("django.utils.timezone.now", return_value=tashkent(MONDAY, 14, 5))
        self.now.start()
        self.addCleanup(self.now.stop)

    def text(self, t, chat=TEACHER_CHAT):
        self.bot.handle_update({"message": {"chat": {"id": chat, "type": "private"}, "from": {"id": chat}, "text": t}})

    def press(self, data, chat=TEACHER_CHAT):
        self.bot.handle_update({"callback_query": {
            "id": "cb", "data": data, "from": {"id": chat},
            "message": {"message_id": 5, "chat": {"id": chat}},
        }})

    def buttons(self):
        return [b for row in self.api.last("editMessageText")["reply_markup"]["inline_keyboard"] for b in row]

    def open_lesson(self):
        self.text(BTN_TAKE_ATTENDANCE)
        lesson_btn = self.api.sent[-1][2]["reply_markup"]["inline_keyboard"][0][0]
        self.press(lesson_btn["callback_data"])
        return Lesson.objects.get(date=MONDAY)

    def test_teacher_contact_links_account(self):
        other = make_teacher("+998 93 555 66 77", "Yangi ustoz")
        self.bot.handle_update({"message": {"chat": {"id": 2002, "type": "private"}, "from": {"id": 2002},
                                            "contact": {"phone_number": "998935556677", "user_id": 2002}}})
        other.refresh_from_db()
        self.assertEqual(other.telegram_chat_id, 2002)
        kb = self.api.sent[-1][2]["reply_markup"]["keyboard"]
        self.assertEqual(kb[0][0]["text"], BTN_TAKE_ATTENDANCE)

    def test_full_flow_mark_and_save(self):
        lesson = self.open_lesson()
        names = [b["text"] for b in self.buttons()]
        self.assertIn("✅ Ali", names)
        self.assertIn("✅ Vali", names)

        self.press(f"T:{AttendanceDraft.objects.get().pk}:{self.vali.pk}")  # ✅ → ❌
        self.assertIn("❌ Vali", [b["text"] for b in self.buttons()])
        self.press(f"S:{AttendanceDraft.objects.get().pk}")

        statuses = dict(Attendance.objects.values_list("student__full_name", "status"))
        self.assertEqual(statuses, {"Ali": "present", "Vali": "absent"})
        self.assertIn("Davomat saqlandi", self.api.last("editMessageText")["text"])
        self.assertFalse(AttendanceDraft.objects.exists())
        # Valining onasiga "kelmadi" xabari navbatga tushdi
        self.assertEqual(Notification.objects.get().kind, "absent")
        lesson.refresh_from_db()
        self.assertEqual(lesson.status, Lesson.Status.DONE)

    def test_cycle_order(self):
        self.open_lesson()
        d = AttendanceDraft.objects.get()
        seen = []
        for _ in range(4):
            self.press(f"T:{d.pk}:{self.ali.pk}")
            seen.append(AttendanceDraft.objects.get().statuses[str(self.ali.pk)])
        self.assertEqual(seen, ["absent", "late", "excused", "present"])

    def test_saved_lesson_cannot_be_reopened(self):
        self.open_lesson()
        self.press(f"S:{AttendanceDraft.objects.get().pk}")
        self.press(f"L:{Lesson.objects.get().pk}")
        self.assertIn("adminga murojaat", self.api.last("editMessageText")["text"])
        self.assertFalse(AttendanceDraft.objects.exists())

    def test_outside_window_rejected(self):
        self.now.stop()
        with patch("django.utils.timezone.now", return_value=tashkent(MONDAY, 10, 0)):
            self.text(BTN_TAKE_ATTENDANCE)
            self.press(f"L:{Lesson.objects.get().pk}")
            answer = self.api.last("answerCallbackQuery")
        self.now.start()
        self.assertIn("13:45", answer["text"])
        self.assertFalse(AttendanceDraft.objects.exists())

    def test_save_after_window_closed_rejected(self):
        self.open_lesson()
        draft = AttendanceDraft.objects.get()
        self.now.stop()
        with patch("django.utils.timezone.now", return_value=tashkent(MONDAY, 18, 0)):
            self.press(f"S:{draft.pk}")
        self.now.start()
        self.assertIn("dars vaqtida", self.api.last("answerCallbackQuery")["text"])
        self.assertFalse(Attendance.objects.exists())

    def test_other_teacher_cannot_open_lesson(self):
        self.text(BTN_TAKE_ATTENDANCE)
        stranger = make_teacher("+998900000077", "Begona")
        stranger.telegram_chat_id = 3003
        stranger.save()
        self.press(f"L:{Lesson.objects.get().pk}", chat=3003)
        self.assertIn("sizniki emas", self.api.last("answerCallbackQuery")["text"])

    def test_parent_cannot_press_teacher_buttons(self):
        self.press("L:1", chat=4004)
        self.assertEqual(self.api.last("answerCallbackQuery")["text"], "Ruxsat yo'q")

    def test_no_lessons_today(self):
        with patch("django.utils.timezone.now", return_value=tashkent(date(2026, 11, 3), 14, 0)):  # seshanba
            self.text(BTN_TAKE_ATTENDANCE)
        self.assertEqual(self.api.sent[-1][1], "Bugun darsingiz yo'q.")

    def test_not_modified_error_ignored(self):
        self.open_lesson()

        def boom(method, **params):
            if method == "editMessageText":
                raise SendError("Bad Request: message is not modified")
            return {}

        self.api.call = boom
        self.press(f"A:{AttendanceDraft.objects.get().pk}")  # xato chiqmasligi kerak
