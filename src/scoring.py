"""Скоринг платёжной дисциплины обучающегося (FR-5).

Используется для решений о предоставлении рассрочки и о переводе договора
в претензионную работу. Модель прозрачная (правила с весами), а не «чёрный ящик»,
что требование NFR-4 (объяснимость решения).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

GRADE_A, GRADE_B, GRADE_C, GRADE_D = "A (низкий риск)", "B (приемлемый)", "C (повышенный)", "D (высокий)"

INSTALLMENTS_BY_GRADE = {"A": 10, "B": 6, "C": 3, "D": 0}


@dataclass
class ScoreResult:
    score: int
    grade: str
    decision: str
    max_installments: int
    reasons: List[str] = field(default_factory=list)


def score_discipline(overdue_ratio: float, max_delay_days: int, avg_delay_days: float,
                     paid_ratio: float) -> ScoreResult:
    """overdue_ratio — доля плана, просроченная на текущий момент;
    max_delay_days / avg_delay_days — глубина просрочек;
    paid_ratio — доля оплаченного плана (0..1).
    """
    score = 100.0
    reasons: List[str] = []

    penalty_ratio = min(40.0, max(0.0, overdue_ratio) * 100 * 0.8)
    if penalty_ratio:
        score -= penalty_ratio
        reasons.append(f"просрочено {overdue_ratio:.1%} плана: -{penalty_ratio:.0f}")

    penalty_max = min(25.0, max(0, max_delay_days) / 4)
    if penalty_max:
        score -= penalty_max
        reasons.append(f"максимальная просрочка {max_delay_days} дн.: -{penalty_max:.0f}")

    penalty_avg = min(20.0, max(0.0, avg_delay_days) / 2)
    if penalty_avg:
        score -= penalty_avg
        reasons.append(f"средняя просрочка {avg_delay_days:.1f} дн.: -{penalty_avg:.0f}")

    if overdue_ratio == 0 and paid_ratio > 0:
        score += 5
        reasons.append("просрочек нет: +5 (бонус добросовестности)")

    score = int(max(0, min(100, round(score))))

    if score >= 80:
        grade, decision = GRADE_A, "Рассрочка одобрена на полный учебный год"
    elif score >= 60:
        grade, decision = GRADE_B, "Рассрочка одобрена с уменьшением числа платежей"
    elif score >= 40:
        grade, decision = GRADE_C, "Укороченный график рассрочки; требуется аванс не менее 30%"
    else:
        grade, decision = GRADE_D, "Перевод в претензионную работу, приостановка предоставления услуг"

    return ScoreResult(
        score=score,
        grade=grade,
        decision=decision,
        max_installments=INSTALLMENTS_BY_GRADE[grade[0]],
        reasons=reasons or ["существенных отклонений не выявлено"],
    )
