"""Расчёт графика платежей, просроченной задолженности и пени (FR-2..FR-4)."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, List

from .models import Contract, Payment, money

ZERO = Decimal("0.00")
# Стандартная договорная неустойка: 1/300 ключевой ставки ЦБ РФ за каждый день просрочки.
PENETY_DIVISOR = Decimal("300")


def add_months(d: date, months: int) -> date:
    total = (d.year * 12 + d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class ScheduleItem:
    number: int
    due_date: date
    amount: Decimal


@dataclass
class ScheduleLine:
    """Строка графика с учётом внесённых платежей (распределение FIFO)."""

    item: ScheduleItem
    paid: Decimal = ZERO

    @property
    def due(self) -> Decimal:
        return money(self.item.amount - self.paid)

    @property
    def is_closed(self) -> bool:
        return self.due <= ZERO


def build_schedule(contract: Contract, first_payment: date) -> List[ScheduleItem]:
    """Ежемесячный график на 1/2/3/4 года обучения (10 платежей в учебном году)."""
    items: List[ScheduleItem] = []
    number = 1
    current = first_payment
    years = max(1, round(contract.total_amount / (contract.net_amount or contract.total_amount)))
    # количество платежей = payments_per_year * number of years, где годы выводим из суммы
    total_installments = contract.payments_per_year * years
    installment = money(contract.net_amount / Decimal(total_installments))
    for _ in range(total_installments):
        items.append(ScheduleItem(number=number, due_date=current, amount=installment))
        number += 1
        current = add_months(current, 1)
    return items


def apply_schedule(contract: Contract, payments: Iterable[Payment], first_payment: date) -> List[ScheduleLine]:
    lines = [ScheduleLine(item=item) for item in build_schedule(contract, first_payment)]
    for payment in sorted(payments, key=lambda p: p.paid_at):
        rest = payment.amount
        for line in lines:
            if rest <= ZERO:
                break
            take = min(rest, line.due)
            if take > ZERO:
                line.paid = money(line.paid + take)
                rest = money(rest - take)
    return lines


def overdue_lines(lines: Iterable[ScheduleLine], today: date) -> List[ScheduleLine]:
    return [ln for ln in lines if ln.due > ZERO and ln.item.due_date < today]


def aging_buckets(lines: Iterable[ScheduleLine], today: date) -> dict:
    """Возрастной анализ дебиторской задолженности (DSO-разбивка)."""
    buckets = {"текущая": ZERO, "1-30": ZERO, "31-60": ZERO, "61-90": ZERO, ">90": ZERO}
    for line in lines:
        if line.due <= ZERO:
            continue
        days = (today - line.item.due_date).days
        if days <= 0:
            buckets["текущая"] = money(buckets["текущая"] + line.due)
        elif days <= 30:
            buckets["1-30"] = money(buckets["1-30"] + line.due)
        elif days <= 60:
            buckets["31-60"] = money(buckets["31-60"] + line.due)
        elif days <= 90:
            buckets["61-90"] = money(buckets["61-90"] + line.due)
        else:
            buckets[">90"] = money(buckets[">90"] + line.due)
    return buckets


def penalty(principal: Decimal, days: int, key_rate_pct=Decimal("21")) -> Decimal:
    """Пени = долг * ставка/100 / 300 * количество дней просрочки."""
    if days <= 0 or principal <= ZERO:
        return ZERO
    return money(principal * (Decimal(str(key_rate_pct)) / Decimal("100")) / PENETY_DIVISOR * Decimal(days))


def arrears_report(contract: Contract, payments: Iterable[Payment], today: date,
                   first_payment: date, key_rate_pct=Decimal("21")) -> dict:
    lines = apply_schedule(contract, payments, first_payment)
    overdue = overdue_lines(lines, today)
    total_overdue = money(sum((ln.due for ln in overdue), ZERO))
    total_penalty = ZERO
    max_days = 0
    for line in overdue:
        days = (today - line.item.due_date).days
        max_days = max(max_days, days)
        total_penalty = money(total_penalty + penalty(line.due, days, key_rate_pct))
    next_due = next((ln.item.due_date for ln in lines if ln.due > ZERO), None)
    paid = money(sum((ln.paid for ln in lines), ZERO))
    return {
        "contract_id": contract.contract_id,
        "plan": contract.net_amount,
        "paid": paid,
        "arrears": money(contract.net_amount - paid),
        "overdue": total_overdue,
        "penalty": total_penalty,
        "total_to_pay": money(total_overdue + total_penalty),
        "max_delay_days": max_days,
        "next_due": next_due.isoformat() if next_due else "-",
        "buckets": aging_buckets(lines, today),
        "paid_ratio": float(paid / contract.net_amount) if contract.net_amount else 0.0,
    }
