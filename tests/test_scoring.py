from unittest import TestCase

from src.scoring import score_discipline


class ScoringTest(TestCase):
    def test_perfect_discipline_is_grade_a(self):
        res = score_discipline(overdue_ratio=0.0, max_delay_days=0,
                               avg_delay_days=0.0, paid_ratio=0.5)
        self.assertEqual(res.score, 100)
        self.assertEqual(res.max_installments, 10)
        self.assertIn("одобрена", res.decision)

    def test_score_monotonically_decreases_with_overdue(self):
        base = dict(max_delay_days=0, avg_delay_days=0.0, paid_ratio=0.5)
        scores = [score_discipline(overdue_ratio=r, **base).score for r in (0, 0.1, 0.2, 0.4)]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_hard_cases_rejected(self):
        res = score_discipline(overdue_ratio=0.6, max_delay_days=200,
                               avg_delay_days=80, paid_ratio=0.1)
        self.assertLess(res.score, 40)
        self.assertEqual(res.max_installments, 0)
        self.assertIn("претензион", res.decision)

    def test_score_bounds(self):
        res = score_discipline(overdue_ratio=1.0, max_delay_days=900, avg_delay_days=300, paid_ratio=0)
        self.assertTrue(0 <= res.score <= 100)
