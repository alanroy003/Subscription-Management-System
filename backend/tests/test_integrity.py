"""Database-level money rules, immutability triggers and the reconciliation job."""
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from core import services
from core.exceptions import exception_handler
from core.integrity import find_issues, run_check
from core.models import Discount, Invoice, InvoiceLine, Payment

from .conftest import client_for

D = Decimal
needs_postgres = pytest.mark.skipif(connection.vendor != "postgresql", reason="triggers are Postgres-only")


def _rejected(fn) -> bool:
    try:
        with transaction.atomic():
            fn()
    except IntegrityError:
        return True
    return False


def _billed_and_confirmed(golden) -> Invoice:
    services.run_billing(date(2026, 1, 15))
    return services.confirm_invoice(Invoice.objects.get())


# ------------------------------------------------------------------ CHECK constraints (SQLite and Postgres)

def test_check_constraints_reject_impossible_money(golden):
    inv = _billed_and_confirmed(golden)
    assert _rejected(lambda: Invoice.objects.filter(pk=inv.pk).update(amount_paid=inv.total + 1))
    assert _rejected(lambda: Invoice.objects.filter(pk=inv.pk).update(subtotal=-1))
    assert _rejected(lambda: Payment.objects.create(invoice=inv, method="cash", amount=0, date=date(2026, 1, 16)))
    assert _rejected(lambda: Discount.objects.create(name="Too much", kind="percent", value=150))
    assert _rejected(lambda: Discount.objects.filter(pk=golden["discount"].pk).update(used_count=99))  # limit is 2


def test_discount_limit_cannot_go_below_usage(admin_user, golden):
    services.run_billing(date(2026, 2, 20))  # uses the volume discount twice
    r = client_for(admin_user).patch(f"/api/discounts/{golden['discount'].pk}", {"usage_limit": 1}, format="json")
    assert r.status_code == 400 and "usage_limit" in r.json()


def test_database_errors_become_400():
    response = exception_handler(IntegrityError('new row violates check constraint "x"'), {})
    assert response.status_code == 400 and "Rejected by the database" in response.data["detail"]


# ------------------------------------------------------------------ triggers (Postgres)

@needs_postgres
def test_issued_invoice_is_immutable_in_the_database(golden):
    inv = _billed_and_confirmed(golden)
    line = inv.lines.first()
    assert _rejected(lambda: Invoice.objects.filter(pk=inv.pk).update(due_date=date(2027, 1, 1)))
    assert _rejected(lambda: InvoiceLine.objects.filter(pk=line.pk).update(description="changed"))
    assert _rejected(lambda: Invoice.objects.filter(pk=inv.pk).delete())
    assert not _rejected(lambda: Invoice.objects.filter(pk=inv.pk).update(sent_at="2026-01-16T10:00:00Z"))


@needs_postgres
def test_status_only_moves_forward_and_payments_are_append_only(golden):
    inv = _billed_and_confirmed(golden)
    services.record_payment(inv, "upi", inv.total, date(2026, 1, 20), "", None)
    payment = Payment.objects.get()
    assert _rejected(lambda: Invoice.objects.filter(pk=inv.pk).update(status="confirmed", amount_paid=0))
    assert _rejected(lambda: Payment.objects.filter(pk=payment.pk).update(amount=1))
    assert _rejected(lambda: Payment.objects.filter(pk=payment.pk).delete())


@needs_postgres
def test_deleting_a_discount_detaches_it_from_issued_lines(golden):
    _billed_and_confirmed(golden)  # cycle 1 used the volume discount
    golden["discount"].delete()
    line = InvoiceLine.objects.get(discount_name="Volume 10%")
    assert line.discount_id is None and line.discount_amount == D("880.00")


# ------------------------------------------------------------------ reconciliation

def test_reconciliation_is_clean_after_normal_billing(golden):
    services.run_billing(date(2026, 3, 20))
    inv = services.confirm_invoice(Invoice.objects.order_by("period_start").first())
    services.record_payment(inv, "upi", D("1000"), date(2026, 2, 1), "part", None)
    issues, counts = find_issues(today=date(2026, 3, 20))
    assert issues == [] and counts["invoices"] == 3


def test_reconciliation_catches_drift(golden, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail

    services.run_billing(date(2026, 1, 15))
    draft = Invoice.objects.get()
    line = draft.lines.order_by("id").last()
    # A draft line edited without updating the header (drafts are editable, so the database allows it).
    InvoiceLine.objects.filter(pk=line.pk).update(unit_price=D("600"), subtotal=D("600"), total=D("690"))
    Discount.objects.filter(pk=golden["discount"].pk).update(used_count=0)
    golden["sub"].__class__.objects.filter(pk=golden["sub"].pk).update(next_invoice_date=date(2026, 1, 1))

    checks = {i["check"] for i in find_issues(today=date(2026, 3, 1))[0]}
    assert checks == {"invoice_total_vs_lines", "discount_usage", "billing_behind"}

    from .conftest import make_user
    make_user("boss@brightloop.test", "admin")
    check = run_check()
    assert check.issue_count >= 3 and len(mail.outbox) == 1 and "issue" in mail.outbox[0].subject


def test_integrity_api_permissions(admin_user, staff_user, golden):
    assert client_for(staff_user).post("/api/integrity/checks/run").status_code == 403
    r = client_for(admin_user).post("/api/integrity/checks/run")
    assert r.status_code == 200 and {i["check"] for i in r.json()["issues"]} == {"billing_behind"}  # fixture is behind
    assert client_for(staff_user).get("/api/integrity/checks").json()["count"] == 1
