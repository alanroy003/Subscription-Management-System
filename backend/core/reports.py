"""Finance summary. All numbers are database aggregates (no per-row Python loops) so the page stays fast at scale."""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth

from .models import Invoice, Payment, Subscription, SubscriptionLine
from .money import MONTHLY_FACTOR, ZERO, add_months, q

MONEY = DecimalField(max_digits=16, decimal_places=2)
OPEN = Invoice.Status.CONFIRMED


def _sum(qs, expr) -> Decimal:
    return qs.aggregate(v=Coalesce(Sum(expr, output_field=MONEY), ZERO, output_field=MONEY))["v"]


def summary(date_from: date | None = None, date_to: date | None = None) -> dict:
    today = date.today()
    date_to = date_to or today
    date_from = date_from or add_months(date_to.replace(day=1), -11)
    balance = ExpressionWrapper(F("total") - F("amount_paid"), output_field=MONEY)

    status_counts = {s: 0 for s in Subscription.Status.values}
    for row in Subscription.objects.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]
    active = status_counts["active"]

    billed_qs = Invoice.objects.filter(status__in=[OPEN, Invoice.Status.PAID], invoice_date__range=(date_from, date_to))
    billed = _sum(billed_qs, "total")
    collected = _sum(Payment.objects.filter(date__range=(date_from, date_to)), "amount")
    open_qs = Invoice.objects.filter(status=OPEN)
    outstanding = _sum(open_qs, balance)
    overdue_qs = open_qs.filter(due_date__lt=today)
    overdue_amount = _sum(overdue_qs, balance)
    overdue_count = overdue_qs.count()

    line_amount = ExpressionWrapper(F("unit_price") * F("quantity"), output_field=MONEY)
    mrr = ZERO
    for row in (SubscriptionLine.objects.filter(subscription__status=Subscription.Status.ACTIVE)
                .values("subscription__plan__billing_period").annotate(v=Sum(line_amount))):
        mrr += (row["v"] or ZERO) * MONTHLY_FACTOR[row["subscription__plan__billing_period"]]
    mrr = q(mrr)
    paying_customers = (Subscription.objects.filter(status=Subscription.Status.ACTIVE)
                        .values("customer").distinct().count())
    arpu = q(mrr / paying_customers) if paying_customers else ZERO
    churned = Subscription.objects.filter(status=Subscription.Status.CLOSED, closed_at__gte=today - timedelta(days=30)).count()
    churn_rate = round(churned * 100 / (active + churned), 1) if (active + churned) else 0.0

    billed_by_month = {r["m"].strftime("%Y-%m"): r["v"] for r in billed_qs.annotate(m=TruncMonth("invoice_date"))
                       .values("m").annotate(v=Sum("total")).order_by()}
    paid_by_month = {r["m"].strftime("%Y-%m"): r["v"] for r in Payment.objects.filter(date__range=(date_from, date_to))
                     .annotate(m=TruncMonth("date")).values("m").annotate(v=Sum("amount")).order_by()}
    series, cursor = [], date_from.replace(day=1)
    while cursor <= date_to:
        key = cursor.strftime("%Y-%m")
        series.append({"month": key, "billed": str(billed_by_month.get(key) or ZERO),
                       "collected": str(paid_by_month.get(key) or ZERO)})
        cursor = add_months(cursor, 1)

    renewals, forecast = {}, {}
    active_qs = Subscription.objects.filter(status=Subscription.Status.ACTIVE)
    for days in (30, 60, 90):
        horizon = today + timedelta(days=days)
        renewals[f"d{days}"] = active_qs.filter(expiry_date__range=(today, horizon)).count()
        due_cash = _sum(open_qs.filter(due_date__lte=horizon), balance)
        upcoming = _sum(SubscriptionLine.objects.filter(subscription__status=Subscription.Status.ACTIVE,
                                                        subscription__next_invoice_date__lte=horizon), line_amount)
        forecast[f"d{days}"] = str(q(due_cash + upcoming))

    at_risk = [
        {"customer_id": r["customer"], "customer_name": r["customer__name"], "overdue_count": r["n"],
         "overdue_amount": str(r["v"])}
        for r in overdue_qs.values("customer", "customer__name").annotate(n=Count("id"), v=Sum(balance))
        .order_by("-v")[:10]
    ]
    top_overdue = [
        {"id": i.id, "number": i.number, "customer_name": i.customer.name, "due_date": str(i.due_date),
         "days_overdue": (today - i.due_date).days, "balance": str(i.balance), "total": str(i.total)}
        for i in overdue_qs.select_related("customer").order_by("due_date")[:10]
    ]

    return {
        "date_from": str(date_from), "date_to": str(date_to),
        "active_subscriptions": active, "status_counts": status_counts,
        "billed": str(billed), "collected": str(collected), "outstanding": str(outstanding),
        "overdue_amount": str(overdue_amount), "overdue_count": overdue_count,
        "mrr": str(mrr), "arpu": str(arpu), "churned_last_30": churned, "churn_rate": churn_rate,
        "revenue_series": series, "renewals": renewals, "forecast": forecast,
        "at_risk": at_risk, "top_overdue": top_overdue,
    }
