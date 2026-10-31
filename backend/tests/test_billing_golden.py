"""Golden billing regression test. Must stay green on every merge."""
from datetime import date
from decimal import Decimal

import pytest

from core import services
from core.models import Invoice
from core.money import add_months, next_period_start
from core.pricing import default_unit_price
from core.reports import summary

D = Decimal


def test_variant_price_extra(golden):
    assert golden["odoo"].price == D("1560")  # 1000 + Odoo 560
    assert default_unit_price(golden["plan"], golden["crm"], golden["odoo"]) == D("1760")  # plan 1200 + 560


def test_period_arithmetic():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert next_period_start(date(2026, 2, 28), "monthly", date(2026, 1, 31)) == date(2026, 3, 31)
    assert next_period_start(date(2026, 1, 1), "weekly") == date(2026, 1, 8)
    assert next_period_start(date(2024, 2, 29), "yearly") == date(2025, 2, 28)


def test_golden_billing_month(golden):
    run = services.run_billing(date(2026, 3, 20))
    assert run.created == 3 and run.failed == 0  # Jan 15, Feb 15, Mar 15 (catch-up)

    inv1, inv2, inv3 = Invoice.objects.order_by("period_start")
    # Cycle 1: CRM 5 x 1760 = 8800, less 10% = 7920, CGST 9% 712.80 + SGST 9% 712.80; support 500 + 90.
    assert inv1.subtotal == D("9300.00")
    assert inv1.discount_total == D("880.00")
    assert inv1.tax_total == D("1515.60")
    assert inv1.total == D("9935.60")
    assert [t["name"] for t in inv1.lines.order_by("id")[0].taxes] == ["CGST", "SGST"]
    assert inv1.period_end == date(2026, 2, 14)
    assert inv1.due_date == date(2026, 1, 30)
    assert inv2.total == D("9935.60")
    # Usage limit of 2 is exhausted: cycle 3 has no discount.
    assert inv3.discount_total == D("0.00") and inv3.total == D("10974.00")
    golden["discount"].refresh_from_db()
    assert golden["discount"].used_count == 2

    # Re-running bills nothing twice.
    again = services.run_billing(date(2026, 3, 20))
    assert again.created == 0 and Invoice.objects.count() == 3

    # Payments: partial then full.
    services.confirm_invoice(inv1)
    services.record_payment(inv1, "upi", D("5000"), date(2026, 2, 1), "part", None)
    inv1.refresh_from_db()
    assert inv1.status == "confirmed" and inv1.balance == D("4935.60") and inv1.is_overdue
    with pytest.raises(services.DomainError):
        services.record_payment(inv1, "upi", D("5000"), date(2026, 2, 2), "too much", None)
    services.record_payment(inv1, "bank_transfer", D("4935.60"), date(2026, 2, 3), "rest", None)
    inv1.refresh_from_db()
    assert inv1.status == "paid" and inv1.balance == 0

    services.confirm_invoice(inv2)
    s = summary(date(2026, 1, 1), date(2026, 3, 31))
    assert s["active_subscriptions"] == 1
    assert D(s["billed"]) == D("19871.20")  # confirmed + paid only
    assert D(s["collected"]) == D("9935.60")
    assert D(s["outstanding"]) == D("9935.60") and s["overdue_count"] == 1
    assert D(s["mrr"]) == D("9300.00")


def test_cancel_releases_discount_usage(golden):
    services.run_billing(date(2026, 1, 15))
    inv = Invoice.objects.get()
    services.cancel_invoice(inv)
    golden["discount"].refresh_from_db()
    assert golden["discount"].used_count == 0


def test_dry_run_changes_nothing(golden):
    run = services.run_billing(date(2026, 3, 20), dry_run=True)
    assert run.created == 3 and Invoice.objects.count() == 0
    golden["sub"].refresh_from_db()
    assert golden["sub"].next_invoice_date == date(2026, 1, 15)


def test_failure_isolation(golden):
    from core.models import Subscription
    broken = Subscription.objects.create(number="SUB-T-2", customer=golden["customer"], plan=golden["plan"],
                                         status="active", start_date=date(2026, 1, 1), next_invoice_date=date(2026, 1, 1))
    run = services.run_billing(date(2026, 1, 20))  # broken has no lines
    assert run.failed == 1 and run.created == 1
    assert not Invoice.objects.filter(subscription=broken).exists()


def test_paused_is_not_billed_and_expiry_auto_closes(golden):
    sub = golden["sub"]
    sub.status = "paused"
    sub.save()
    assert services.run_billing(date(2026, 2, 20)).created == 0
    sub.status, sub.expiry_date = "active", date(2026, 3, 1)
    sub.plan.auto_close = True
    sub.plan.save()
    sub.save()
    services.run_billing(date(2026, 3, 20))
    sub.refresh_from_db()
    assert sub.status == "closed"
    assert Invoice.objects.filter(subscription=sub).count() == 2  # Jan 15, Feb 15; Mar 15 is past expiry


def test_igst_for_other_state(golden):
    golden["customer"].state = "Maharashtra"
    golden["customer"].save()
    services.run_billing(date(2026, 1, 15))
    line = Invoice.objects.get().lines.order_by("id")[0]
    assert [t["name"] for t in line.taxes] == ["IGST"] and line.tax_amount == D("1425.60")


def test_confirmed_invoice_cannot_be_reconfirmed_or_cancelled_after_payment(golden):
    services.run_billing(date(2026, 1, 15))
    inv = services.confirm_invoice(Invoice.objects.get())
    with pytest.raises(services.DomainError):
        services.confirm_invoice(inv)
    services.record_payment(inv, "cash", D("100"), date(2026, 1, 16), "", None)
    with pytest.raises(services.DomainError):
        services.cancel_invoice(inv)
