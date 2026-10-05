from decimal import Decimal
from unittest import TestCase

from src.analytics import dunning_list, irr, npv, portfolio_summary


def make_report(plan=1000, paid=600, overdue=300, penalty=30):
    return {"plan": Decimal(plan), "paid": Decimal(paid), "arrears": Decimal(plan - paid),
            "overdue": Decimal(overdue), "penalty": Decimal(penalty),
            "total_to_pay": Decimal(overdue + penalty), "max_delay_days": 40}


class NpvTest(TestCase):
    def test_npv_at_zero_rate_is_sum(self):
        self.assertAlmostEqual(npv(0.0, [100, 100, 100]), 300)

    def test_irr_of_bank_deposit(self):
        # кладём 100, получаем 110 через год -> IRR = 10%
        self.assertAlmostEqual(irr([-100, 110]), 0.10, places=6)

    def test_irr_of_installment_is_positive_for_provider(self):
        flows = [-1000] + [100] * 10
        self.assertGreater(irr(flows), 0.0)


class PortfolioTest(TestCase):
    def test_collection_rate(self):
        s = portfolio_summary([make_report(), make_report()])
        self.assertAlmostEqual(s["collection_rate"], 0.6)
        self.assertEqual(s["contracts"], 2)

    def test_dunning_sorted_desc(self):
        rows = [make_report(overdue=100), make_report(overdue=900)]
        self.assertEqual(dunning_list(rows)[0]["overdue"], Decimal(900))
