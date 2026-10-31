"""Finance summary. Nine database aggregates, run in parallel, so the dashboard stays fast at scale."""
from datetime import date, timedelta

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth

from .models import Invoice, Payment, Subscription, SubscriptionLine
from .money import MONTHLY_FACTOR, ZERO, add_months, q
from .parallel import run_parallel

MONEY = DecimalField(max_digits=16, decimal_places=2)
OPEN = Invoice.Status.CONFIRMED
ACTIVE = Subscription.Status.ACTIVE
HORIZONS = (30, 60, 90)


def m(value) -> str:
    return str(q(value or ZERO))


def _money_sum(expr, **filters):
    return Coalesce(Sum(expr, filter=Q(**filters) if filters else None, output_field=MONEY), ZERO, output_field=MONEY)


def summary(date_from: date | None = None, date_to: date | None = None) -> dict:
    today = date.today()
    date_to = date_to or today
    date_from = date_from or add_months(date_to.replace(day=1), -11)
    balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=MONEY)
    line_amount = ExpressionWrapper(F("unit_price") * F("quantity"), output_field=MONEY)
    billed_qs = Invoice.objects.filter(status__in=[OPEN, Invoice.Status.PAID], invoice_date__range=(date_from, date_to))
    overdue_qs = Invoice.objects.filter(status=OPEN, due_date__lt=today)

    def status_counts():
        return {r["status"]: r["n"] for r in Subscription.objects.values("status").annotate(n=Count("id")).order_by()}

    def sub_stats():
        agg = {
            "churned": Count(
                "id", filter=Q(status=Subscription.Status.CLOSED, closed_at__gte=today - timedelta(days=30))
            ),
            "paying": Count("customer", distinct=True, filter=Q(status=ACTIVE)),
        }
        for d in HORIZONS:
            agg[f"r{d}"] = Count("id", filter=Q(status=ACTIVE, expiry_date__range=(today, today + timedelta(days=d))))
        return Subscription.objects.aggregate(**agg)

    def invoice_stats():
        agg = {
            "billed": _money_sum(
                "total", status__in=[OPEN, Invoice.Status.PAID], invoice_date__range=(date_from, date_to)
            ),
            "outstanding": _money_sum(balance, status=OPEN),
            "overdue_amount": _money_sum(balance, status=OPEN, due_date__lt=today),
            "overdue_count": Count("id", filter=Q(status=OPEN, due_date__lt=today)),
        }
        for d in HORIZONS:
            agg[f"due{d}"] = _money_sum(balance, status=OPEN, due_date__lte=today + timedelta(days=d))
        return Invoice.objects.aggregate(**agg)

    def collected():
        return Payment.objects.filter(date__range=(date_from, date_to)).aggregate(v=_money_sum("amount"))["v"]

    def recurring():
        agg = {"v": Sum(line_amount)}
        for d in HORIZONS:
            agg[f"up{d}"] = _money_sum(line_amount, subscription__next_invoice_date__lte=today + timedelta(days=d))
        return list(SubscriptionLine.objects.filter(subscription__status=ACTIVE)
                    .values("subscription__plan__billing_period").annotate(**agg).order_by())

    def billed_series():
        return {r["m"].strftime("%Y-%m"): r["v"] for r in billed_qs.annotate(m=TruncMonth("invoice_date"))
                .values("m").annotate(v=Sum("total")).order_by()}

    def collected_series():
        return {r["m"].strftime("%Y-%m"): r["v"] for r in Payment.objects.filter(date__range=(date_from, date_to))
                .annotate(m=TruncMonth("date")).values("m").annotate(v=Sum("amount")).order_by()}

    def at_risk():
        return [
            {"customer_id": r["customer"], "customer_name": r["customer__name"], "overdue_count": r["n"],
             "overdue_amount": m(r["v"])}
            for r in overdue_qs.values("customer", "customer__name").annotate(n=Count("id"), v=Sum(balance))
            .order_by("-v")[:10]
        ]

    def top_overdue():
        return [
            {"id": i.id, "number": i.number, "customer_name": i.customer.name, "due_date": str(i.due_date),
             "days_overdue": (today - i.due_date).days, "balance": m(i.balance), "total": m(i.total)}
            for i in overdue_qs.select_related("customer").order_by("due_date")[:10]
        ]

    r = run_parallel({
        "status_counts": status_counts, "sub_stats": sub_stats, "invoice_stats": invoice_stats,
        "collected": collected, "recurring": recurring, "billed_series": billed_series,
        "collected_series": collected_series, "at_risk": at_risk, "top_overdue": top_overdue,
    })

    counts = {s: 0 for s in Subscription.Status.values} | r["status_counts"]
    active = counts["active"]
    subs, inv = r["sub_stats"], r["invoice_stats"]
    mrr = q(sum(((row["v"] or ZERO) * MONTHLY_FACTOR[row["subscription__plan__billing_period"]]
                 for row in r["recurring"]), ZERO))
    arpu = q(mrr / subs["paying"]) if subs["paying"] else ZERO
    churned = subs["churned"]

    series, cursor = [], date_from.replace(day=1)
    while cursor <= date_to:
        key = cursor.strftime("%Y-%m")
        series.append({"month": key, "billed": m(r["billed_series"].get(key)),
                       "collected": m(r["collected_series"].get(key))})
        cursor = add_months(cursor, 1)

    forecast = {}
    for d in HORIZONS:
        upcoming = sum((row[f"up{d}"] for row in r["recurring"]), ZERO)
        forecast[f"d{d}"] = str(q(inv[f"due{d}"] + upcoming))

    return {
        "date_from": str(date_from), "date_to": str(date_to),
        "active_subscriptions": active, "status_counts": counts,
        "billed": m(inv["billed"]), "collected": m(r["collected"]), "outstanding": m(inv["outstanding"]),
        "overdue_amount": m(inv["overdue_amount"]), "overdue_count": inv["overdue_count"],
        "mrr": str(mrr), "arpu": str(arpu), "churned_last_30": churned,
        "churn_rate": round(churned * 100 / (active + churned), 1) if (active + churned) else 0.0,
        "revenue_series": series, "renewals": {f"d{d}": subs[f"r{d}"] for d in HORIZONS}, "forecast": forecast,
        "at_risk": r["at_risk"], "top_overdue": r["top_overdue"],
    }
