"""Money and period arithmetic. Pure functions, Decimal only."""
import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def q(value) -> Decimal:
    """The one rounding rule: half-up to 2 decimal places."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def next_period_start(start: date, period: str, anchor: date | None = None) -> date:
    """Start of the following billing period. `anchor` keeps month-end anchors stable (Jan 31 -> Feb 28 -> Mar 31)."""
    if period == "daily":
        return start + timedelta(days=1)
    if period == "weekly":
        return start + timedelta(days=7)
    anchor = anchor or start
    if period == "monthly":
        months = (start.year - anchor.year) * 12 + (start.month - anchor.month) + 1
        return add_months(anchor, months)
    if period == "yearly":
        return add_months(anchor, ((start.year - anchor.year) + 1) * 12)
    raise ValueError(f"Unknown billing period {period}")


MONTHLY_FACTOR = {
    "daily": Decimal(365) / Decimal(12),
    "weekly": Decimal(52) / Decimal(12),
    "monthly": Decimal(1),
    "yearly": Decimal(1) / Decimal(12),
}


def monthly_amount(amount: Decimal, period: str) -> Decimal:
    return q(amount * MONTHLY_FACTOR[period])
