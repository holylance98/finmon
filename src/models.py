"""Доменные модели модуля финансового мониторинга.

Только стандартная библиотека Python: проект должен запускаться
на любой машине без установки внешних зависимостей.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

MONEY = Decimal("0.01")


def money(value) -> Decimal:
    """Приводит значение к денежному формату (2 знака, банковское округление)."""
    if isinstance(value, Decimal):
        return value.quantize(MONEY, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Contract:
    """Договор об оказании платных образовательных услуг."""

    contract_id: str
    student_name: str
    program: str
    faculty: str
    signed_at: date
    total_amount: Decimal
    payments_per_year: int = 10
    discount_pct: Decimal = Decimal("0")
    status: str = "active"

    @property
    def net_amount(self) -> Decimal:
        """Сумма к оплате с учётом скидки."""
        return money(self.total_amount * (Decimal("1") - self.discount_pct / Decimal("100")))

    @property
    def installment_amount(self) -> Decimal:
        """Размер одного платежа по графику."""
        return money(self.net_amount / Decimal(self.payments_per_year))

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True)
class Payment:
    """Факт поступления от обучающегося."""

    contract_id: str
    paid_at: date
    amount: Decimal
    purpose: str = "очередной платёж"


def parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Неизвестный формат даты: {value!r}")


def load_contracts(rows) -> list:
    result = []
    for r in rows:
        result.append(
            Contract(
                contract_id=r["contract_id"].strip(),
                student_name=r["student_name"].strip(),
                program=r["program"].strip(),
                faculty=r["faculty"].strip(),
                signed_at=parse_date(r["signed_at"]),
                total_amount=money(r["total_amount"]),
                payments_per_year=int(r.get("payments_per_year") or 10),
                discount_pct=Decimal(r.get("discount_pct") or 0),
                status=(r.get("status") or "active").strip(),
            )
        )
    return result


def load_payments(rows) -> list:
    return [
        Payment(
            contract_id=r["contract_id"].strip(),
            paid_at=parse_date(r["paid_at"]),
            amount=money(r["amount"]),
            purpose=(r.get("purpose") or "очередной платёж").strip(),
        )
        for r in rows
    ]
