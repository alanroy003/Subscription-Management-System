"""Nightly reconciliation: prove the money data still adds up.

The database already rejects impossible rows (CHECK constraints, immutability triggers). This job catches what a
single-row rule cannot: totals that disagree with their lines, paid amounts that disagree with the payment ledger,
discount usage counters that drifted, and subscriptions the billing run skipped.
"""
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Discount, IntegrityCheck, Invoice, InvoiceLine, Payment, Subscription
from .money import ZERO

MONEY = DecimalField(max_digits=16, decimal_places=2)
MAX_LISTED = 200


def _line_sum(field: str):
    return Coalesce(
        Subquery(
            InvoiceLine.objects.filter(invoice=OuterRef("pk")).values("invoice").annotate(v=Sum(field)).values("v"),
            output_field=MONEY,
        ),
        Value(ZERO),
        output_field=MONEY,
    )


def _paid_sum():
    return Coalesce(
        Subquery(
            Payment.objects.filter(invoice=OuterRef("pk")).values("invoice").annotate(v=Sum("amount")).values("v"),
            output_field=MONEY,
        ),
        Value(ZERO),
        output_field=MONEY,
    )


def find_issues(today: date | None = None) -> tuple[list[dict], dict]:
    """Returns (issues, counts). Each issue: {check, ref, detail}."""
    today = today or date.today()
    issues: list[dict] = []

    def add(check: str, ref: str, detail: str) -> None:
        issues.append({"check": check, "ref": ref, "detail": detail})

    totals = (
        Invoice.objects.annotate(
            l_subtotal=_line_sum("subtotal"), l_discount=_line_sum("discount_amount"),
            l_tax=_line_sum("tax_amount"), l_total=_line_sum("total"),
        )
        .filter(~Q(subtotal=F("l_subtotal")) | ~Q(discount_total=F("l_discount"))
                | ~Q(tax_total=F("l_tax")) | ~Q(total=F("l_total")))
        .values("number", "total", "l_total")
    )
    for row in totals:
        add("invoice_total_vs_lines", row["number"], f"total {row['total']} but lines sum to {row['l_total']}")

    for row in (Invoice.objects.annotate(ledger=_paid_sum()).filter(~Q(amount_paid=F("ledger")))
                .values("number", "amount_paid", "ledger")):
        add(
            "invoice_paid_vs_payments",
            row["number"],
            f"amount_paid {row['amount_paid']} but payments sum to {row['ledger']}",
        )

    for number in (Invoice.objects.filter(status=Invoice.Status.CONFIRMED, total__gt=0, amount_paid__gte=F("total"))
                   .values_list("number", flat=True)):
        add("invoice_status", number, "fully paid but still marked confirmed")

    usage: dict[int, int] = {}
    for applied in (Invoice.objects.exclude(status=Invoice.Status.CANCELLED).exclude(applied_discounts=[])
                    .values_list("applied_discounts", flat=True).iterator(chunk_size=5000)):
        for discount_id in applied or []:
            usage[discount_id] = usage.get(discount_id, 0) + 1
    for d in Discount.objects.only("id", "name", "used_count"):
        if d.used_count != usage.get(d.id, 0):
            add("discount_usage", d.name, f"used_count {d.used_count} but {usage.get(d.id, 0)} invoices use it")

    behind = (
        Subscription.objects.filter(status=Subscription.Status.ACTIVE, next_invoice_date__lt=today - timedelta(days=1))
        .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gt=F("next_invoice_date")))
        .values_list("number", "next_invoice_date")
    )
    for number, due in behind:
        add("billing_behind", number, f"period starting {due} was not billed")

    counts = {
        "invoices": Invoice.objects.count(),
        "payments": Payment.objects.count(),
        "discounts": Discount.objects.count(),
        "active_subscriptions": Subscription.objects.filter(status=Subscription.Status.ACTIVE).count(),
    }
    return issues, counts


def run_check(notify: bool = True, user=None) -> IntegrityCheck:
    started = timezone.now()
    issues, counts = find_issues()
    check = IntegrityCheck.objects.create(
        started_at=started, finished_at=timezone.now(), issue_count=len(issues), issues=issues[:MAX_LISTED],
        counts=counts, triggered_by=user if user and getattr(user, "is_authenticated", False) else None,
    )
    if issues and notify:
        _alert_admins(check)
    return check


def _alert_admins(check: IntegrityCheck) -> None:
    from accounts.models import User
    recipients = list(User.objects.filter(role=User.Role.ADMIN, is_active=True).values_list("email", flat=True))
    if not recipients:
        return
    lines = "\n".join(f"- [{i['check']}] {i['ref']}: {i['detail']}" for i in check.issues[:50])
    send_mail(
        f"Brightloop data check found {check.issue_count} issue(s)",
        f"The reconciliation run at {check.finished_at:%Y-%m-%d %H:%M} found {check.issue_count} issue(s):"
        f"\n\n{lines}\n\n"
        f"Open {settings.FRONTEND_URL}/billing to review.",
        settings.DEFAULT_FROM_EMAIL,
        recipients,
        fail_silently=True,
    )
