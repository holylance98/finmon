"""Аналитика портфеля и экономическая эффективность рассрочки (FR-7)."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, List, Sequence


def npv(rate: float, flows: Sequence[float]) -> float:
    return sum(cf / (1.0 + rate) ** i for i, cf in enumerate(flows))


def irr(flows: Sequence[float], low: float = -0.95, high: float = 5.0, tol: float = 1e-9) -> float:
    """Внутренняя норма доходности графика платежей (метод дихотомии, без внешних библиотек)."""
    f_low, f_high = npv(low, flows), npv(high, flows)
    if f_low * f_high > 0:
        raise ValueError("IRR не существует на выбранном интервале")
    for _ in range(300):
        mid = (low + high) / 2
        f_mid = npv(mid, flows)
        if abs(f_mid) < tol:
            return mid
        if f_low * f_mid <= 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2


def portfolio_summary(reports: Iterable[dict]) -> dict:
    rows = list(reports)
    total_plan = sum(r["plan"] for r in rows)
    total_paid = sum(r["paid"] for r in rows)
    total_overdue = sum(r["overdue"] for r in rows)
    total_penalty = sum(r["penalty"] for r in rows)
    delinquent = [r for r in rows if r["overdue"] > 0]
    return {
        "contracts": len(rows),
        "plan": total_plan,
        "paid": total_paid,
        "arrears": sum(r["arrears"] for r in rows),
        "overdue": total_overdue,
        "penalty": total_penalty,
        "collection_rate": float(total_paid / total_plan) if total_plan else 0.0,
        "delinquent_share": float(len(delinquent) / len(rows)) if rows else 0.0,
        "avg_max_delay": round(sum(r["max_delay_days"] for r in rows) / len(rows), 1) if rows else 0,
    }


def dunning_list(reports: Iterable[dict], min_overdue: Decimal = Decimal("0")) -> List[dict]:
    """Очередь претензионной работы, отсортированная по сумме к взысканию."""
    return sorted((r for r in reports if r["overdue"] > min_overdue),
                  key=lambda r: r["total_to_pay"], reverse=True)
