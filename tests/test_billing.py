from datetime import date
from decimal import Decimal
from unittest import TestCase

from src.billing import aging_buckets, apply_schedule, arrears_report, build_schedule, penalty
from src.models import Contract, Payment


class ContractFactory:
    @staticmethod
    def make(amount="288000", per_year=10, discount="10"):
        return Contract("DM-1", "Тест Тест Тест", "ПИ", "ФИТ",
                        date(2025, 9, 1), Decimal(amount), int(per_year), Decimal(discount))


class ScheduleTest(TestCase):
    def test_net_amount_respects_discount(self):
        self.assertEqual(ContractFactory.make().net_amount, Decimal("259200.00"))

    def test_schedule_sums_to_net_amount(self):
        c = ContractFactory.make()
        items = build_schedule(c, date(2025, 9, 1))
        self.assertAlmostEqual(sum(i.amount for i in items), c.net_amount, places=2)

    def test_schedule_is_monthly(self):
        items = build_schedule(ContractFactory.make(), date(2025, 9, 1))
        self.assertEqual((items[0].due_date, items[1].due_date), (date(2025, 9, 1), date(2025, 10, 1)))

    def test_fully_paid_contract_has_no_arrears(self):
        c = ContractFactory.make()
        items = build_schedule(c, date(2025, 9, 1))
        payments = [Payment("DM-1", i.due_date, i.amount) for i in items]
        rep = arrears_report(c, payments, date(2026, 6, 1), date(2025, 9, 1))
        self.assertEqual(rep["arrears"], Decimal("0.00"))
        self.assertEqual(rep["overdue"], Decimal("0.00"))

    def test_partial_payment_creates_arrears(self):
        c = ContractFactory.make()
        rep = arrears_report(c, [Payment("DM-1", date(2025, 9, 3), Decimal("25920"))],
                             date(2025, 12, 1), date(2025, 9, 1))
        self.assertEqual(rep["paid"], Decimal("25920.00"))
        # не внесены октябрьский и ноябрьский платежи: 25920 * 2
        self.assertEqual(rep["overdue"], Decimal("51840.00"))
        self.assertGreater(rep["penalty"], Decimal("0.00"))

    def test_aging_buckets_split_debt(self):
        c = ContractFactory.make()
        lines = apply_schedule(c, [], date(2025, 9, 1))
        buckets = aging_buckets(lines, date(2025, 12, 1))
        self.assertGreater(buckets[">90"], Decimal("0.00"))       # сентябрьский платёж
        self.assertGreater(buckets["1-30"], Decimal("0.00"))       # ноябрьский платёж
        self.assertEqual(sum(buckets.values()), c.net_amount)      # долг не теряется

    def test_penalty_formula(self):
        # 100 000 * 21% / 300 * 10 дней = 700.00
        self.assertEqual(penalty(Decimal("100000"), 10, Decimal("21")), Decimal("700.00"))

    def test_penalty_zero_without_delay(self):
        self.assertEqual(penalty(Decimal("100000"), 0), Decimal("0.00"))
