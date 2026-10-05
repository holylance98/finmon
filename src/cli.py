"""CLI-интерфейс FinMon.

Запуск: python -m src.cli report --today 2026-06-01
"""
from __future__ import annotations

import argparse
import csv
import os
from datetime import date
from decimal import Decimal

from .analytics import dunning_list, npv, portfolio_summary
from .billing import add_months, arrears_report
from .models import load_contracts, load_payments, parse_date
from .scoring import score_discipline
from .security import AuditLog, mask_name

DEFAULT_FIRST_PAYMENT = date(2025, 9, 1)


def _read_csv(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _avg_delay(payments, first_payment: date) -> float:
    """Средняя задержка платежей относительно эталонного графика."""
    if not payments:
        return 0.0
    delays = []
    for index, payment in enumerate(sorted(payments, key=lambda x: x.paid_at)):
        expected = add_months(first_payment, index)
        delays.append(max(0, (payment.paid_at - expected).days))
    return sum(delays) / len(delays)


def cmd_report(args):
    contracts = load_contracts(_read_csv(args.contracts))
    payments = load_payments(_read_csv(args.payments))
    by_contract = {}
    for p in payments:
        by_contract.setdefault(p.contract_id, []).append(p)

    today = parse_date(args.today)
    rows = []
    log = AuditLog()
    for c in contracts:
        if not c.is_active:
            continue
        rep = arrears_report(c, by_contract.get(c.contract_id, []), today,
                             DEFAULT_FIRST_PAYMENT, Decimal(args.key_rate))
        rep["student"] = c.student_name if args.unmask else mask_name(c.student_name)
        rep["program"] = c.program
        rep["faculty"] = c.faculty
        rep["score"] = score_discipline(
            overdue_ratio=float(rep["overdue"] / rep["plan"]) if rep["plan"] else 0.0,
            max_delay_days=rep["max_delay_days"],
            avg_delay_days=_avg_delay(by_contract.get(c.contract_id, []), DEFAULT_FIRST_PAYMENT),
            paid_ratio=rep["paid_ratio"],
        )
        rows.append(rep)
        log.add(actor="cli", action="build_report", details=f"contract={c.contract_id}")

    header = ["contract_id", "student", "faculty", "program", "plan", "paid",
              "arrears", "overdue", "penalty", "total_to_pay", "max_delay_days",
              "next_due", "score", "grade", "decision"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(header)
        for r in rows:
            writer.writerow([r["contract_id"], r["student"], r["faculty"], r["program"],
                             r["plan"], r["paid"], r["arrears"], r["overdue"], r["penalty"],
                             r["total_to_pay"], r["max_delay_days"], r["next_due"],
                             r["score"].score, r["score"].grade, r["score"].decision])

    summary = portfolio_summary(rows)
    print("=== Сводка портфеля ===")
    for key in ("contracts", "plan", "paid", "arrears", "overdue", "penalty",
                "collection_rate", "delinquent_share", "avg_max_delay"):
        print(f"{key:>18}: {summary[key]}")
    print("\n=== Претензионная очередь (top-5) ===")
    for r in dunning_list(rows)[:5]:
        print(f"{r['contract_id']}  {r['student']:<22} долг={r['overdue']}  "
              f"пени={r['penalty']}  рейтинг={r['score'].score} ({r['score'].grade})")
    print(f"\nОтчёт сохранён: {args.out}")
    print(f"Целостность журнала операций: {'OK' if log.verify() else 'НАРУШЕНА'}")


def cmd_irr(args):
    """Экономика беспроцентной рассрочки: упущенная выгода и безубыточный платёж."""
    plan = float(args.plan)
    n = args.installments
    annual = float(args.annual_rate) / 100
    monthly = (1 + annual) ** (1 / 12) - 1          # эквивалентная месячная ставка
    pmt = plan / n
    npv_value = npv(monthly, [0.0] + [pmt] * n)      # дисконтированный доход рассрочки
    annuity_factor = sum(1 / (1 + monthly) ** i for i in range(1, n + 1))
    breakeven = plan / annuity_factor
    print(f"Сумма договора: {plan:,.2f} руб., {n} равных платежей по {pmt:,.2f} руб.")
    print(f"Альтернативная доходность: {annual:.1%} годовых ({monthly:.4%} месячных)")
    print(f"Текущая стоимость рассрочки: {npv_value:,.2f} руб.")
    print(f"Упущенная выгода вуза: {plan - npv_value:,.2f} руб. "
          f"({(plan - npv_value) / plan:.2%} суммы договора)")
    print(f"Безубыточный платёж (компенсирует отсрочку): {breakeven:,.2f} руб., "
          f"+{(breakeven / pmt - 1) * 100:.2f}% к обычному платежу")


def build_parser():
    parser = argparse.ArgumentParser(prog="finmon", description="Финансовый мониторинг договоров")
    sub = parser.add_subparsers(dest="command", required=True)

    rep = sub.add_parser("report", help="Сформировать отчёт по задолженности")
    rep.add_argument("--contracts", default="data/contracts_sample.csv")
    rep.add_argument("--payments", default="data/payments_sample.csv")
    rep.add_argument("--today", default=date.today().isoformat())
    rep.add_argument("--key-rate", default="21", help="Ключевая ставка ЦБ РФ, %%")
    rep.add_argument("--out", default="out/report.csv")
    rep.add_argument("--unmask", action="store_true",
                     help="Не обезличивать ФИО (только для авторизованного отчёта)")
    rep.set_defaults(func=cmd_report)

    inv = sub.add_parser("economics", help="Экономика рассрочки: упущенная выгода")
    inv.add_argument("--plan", default="288000")
    inv.add_argument("--installments", type=int, default=10)
    inv.add_argument("--annual-rate", default="21",
                     help="Альтернативная доходность размещения средств, %%")
    inv.set_defaults(func=cmd_irr)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    out_dir = os.path.dirname(args.out) if hasattr(args, "out") else ""
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
