from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.academics.models import Enrollment, Student
from apps.academics.tests.factories import enroll, make_admin, make_group
from apps.finance import billing
from apps.finance.models import Invoice


class MonthChargeTests(TestCase):
    def setUp(self):
        self.group = make_group()  # Du/Chor/Ju, 300 000 / 25 000

    def test_full_month_is_monthly_price_even_with_13_lessons(self):
        e = enroll(self.group, date(2026, 10, 1))
        # 2026-yil dekabr: Du/Chor/Ju — 13 dars (13 × 25k = 325k), baribir 300 000
        c = billing.calc_month_charge(e, 2026, 12)
        self.assertTrue(c.full_month)
        self.assertEqual(c.lessons_count, 13)
        self.assertEqual(c.amount, 300_000)

    def test_joined_mid_month_pays_remaining_lessons(self):
        # TZ misoli: 15-noyabrda qo'shildi → 16,18,20,23,25,27,30 = 7 dars
        e = enroll(self.group, date(2026, 11, 15))
        c = billing.calc_month_charge(e, 2026, 11)
        self.assertFalse(c.full_month)
        self.assertEqual(c.lessons_count, 7)
        self.assertEqual(c.amount, 175_000)

    def test_joined_on_lesson_day_counts_that_lesson(self):
        e = enroll(self.group, date(2026, 11, 16))  # dushanba
        self.assertEqual(billing.calc_month_charge(e, 2026, 11).lessons_count, 7)

    def test_partial_month_never_exceeds_monthly_price(self):
        e = enroll(self.group, date(2026, 12, 2))  # dekabrda 2-dan keyin 13 dars × 25k = 325k
        c = billing.calc_month_charge(e, 2026, 12)
        self.assertEqual(c.lessons_count, 13)
        self.assertEqual(c.amount, 300_000)

    def test_left_mid_month(self):
        # TZ misoli: 13-noyabrda ketdi → 2,4,6,9,11,13 = 6 dars
        e = enroll(self.group, date(2026, 10, 1), left_at=date(2026, 11, 13))
        c = billing.calc_month_charge(e, 2026, 11)
        self.assertEqual((c.lessons_count, c.amount), (6, 150_000))

    def test_not_enrolled_that_month(self):
        e = enroll(self.group, date(2026, 11, 15))
        self.assertIsNone(billing.calc_month_charge(e, 2026, 10))

    def test_percent_discount(self):
        e = enroll(self.group, date(2026, 10, 1), discount_type=Enrollment.DiscountType.PERCENT, discount_value=10)
        c = billing.calc_month_charge(e, 2026, 11)
        self.assertEqual((c.base_amount, c.discount_amount, c.amount), (300_000, 30_000, 270_000))

    def test_fixed_discount(self):
        e = enroll(self.group, date(2026, 10, 1), discount_type=Enrollment.DiscountType.FIXED, discount_value=50_000)
        self.assertEqual(billing.calc_month_charge(e, 2026, 11).amount, 250_000)

    def test_custom_group_prices(self):
        self.group.monthly_price, self.group.lesson_price = 400_000, 35_000
        self.group.save()
        e = enroll(self.group, date(2026, 11, 15))
        self.assertEqual(billing.calc_month_charge(e, 2026, 11).amount, 7 * 35_000)


class DueDateTests(TestCase):
    def test_regular_due_day_5(self):
        e = enroll(make_group(), date(2026, 10, 1))
        self.assertEqual(billing.calc_due_date(e, 2026, 11), date(2026, 11, 5))

    def test_new_student_gets_extra_days(self):
        e = enroll(make_group(), date(2026, 11, 15))
        self.assertEqual(billing.calc_due_date(e, 2026, 11), date(2026, 11, 20))


class PaymentFlowTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.group = make_group()
        self.e = enroll(self.group, date(2026, 10, 1))
        self.student = self.e.student

    def test_generate_invoices_is_idempotent(self):
        self.assertEqual(billing.generate_month_invoices(2026, 11), 1)
        self.assertEqual(billing.generate_month_invoices(2026, 11), 1)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_partial_then_full_payment_fifo(self):
        billing.generate_month_invoices(2026, 10)
        billing.generate_month_invoices(2026, 11)
        billing.accept_payment(self.student, 400_000, user=self.admin)
        oct_inv, nov_inv = Invoice.objects.order_by("period")
        self.assertEqual((oct_inv.status, oct_inv.paid_amount), (Invoice.Status.PAID, 300_000))
        self.assertEqual((nov_inv.status, nov_inv.paid_amount), (Invoice.Status.PARTIAL, 100_000))
        self.assertEqual(billing.student_balance(self.student), -200_000)

    def test_advance_payment_covers_next_invoice(self):
        billing.accept_payment(self.student, 300_000, user=self.admin)
        self.assertEqual(billing.student_balance(self.student), 300_000)
        billing.generate_month_invoices(2026, 11)
        self.assertEqual(Invoice.objects.get().status, Invoice.Status.PAID)

    def test_cancel_payment_reopens_invoice_and_keeps_record(self):
        billing.generate_month_invoices(2026, 11)
        p = billing.accept_payment(self.student, 300_000, user=self.admin)
        billing.cancel_payment(p, user=self.admin, reason="Xato kiritildi")
        self.assertEqual(Invoice.objects.get().status, Invoice.Status.OPEN)
        p.refresh_from_db()
        self.assertTrue(p.is_cancelled)
        with self.assertRaises(ValidationError):
            billing.cancel_payment(p, user=self.admin, reason="yana")

    def test_receipt_numbers_are_sequential(self):
        a = billing.accept_payment(self.student, 100_000, user=self.admin)
        b = billing.accept_payment(self.student, 100_000, user=self.admin)
        self.assertEqual(int(b.receipt_no.split("-")[1]), int(a.receipt_no.split("-")[1]) + 1)


class LeaveAndRefundTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.e = enroll(make_group(), date(2026, 10, 1))
        self.student = self.e.student
        billing.generate_month_invoices(2026, 11)
        billing.generate_month_invoices(2026, 12)
        billing.accept_payment(self.student, 300_000, user=self.admin)  # noyabr to'langan

    def test_left_mid_month_refund(self):
        refundable = billing.process_leave(self.e, date(2026, 11, 13), user=self.admin)
        self.assertEqual(refundable, 150_000)
        nov, dec = Invoice.objects.order_by("period")
        self.assertEqual((nov.amount, nov.status), (150_000, Invoice.Status.PAID))
        self.assertEqual(dec.status, Invoice.Status.VOID)
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, Student.Status.LEFT)

        billing.give_refund(self.student, 150_000, user=self.admin, reason="Guruhdan ketdi")
        self.assertEqual(billing.student_balance(self.student), 0)

    def test_cannot_refund_more_than_overpaid(self):
        billing.process_leave(self.e, date(2026, 11, 13), user=self.admin)
        with self.assertRaises(ValidationError):
            billing.give_refund(self.student, 150_001, user=self.admin, reason="x")
