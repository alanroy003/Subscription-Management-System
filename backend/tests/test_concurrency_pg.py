"""Concurrency guarantees that only a real Postgres can prove (row locks, ON CONFLICT numbering).

Run with TEST_DATABASE_URL pointing at a disposable Postgres; skipped on SQLite.
"""
import threading
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection, connections

from core import services
from core.models import Discount, Invoice, Subscription, SubscriptionLine

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="needs Postgres (set TEST_DATABASE_URL)"),
]


def _clone_subscriptions(golden, count, start):
    """Copies of the golden subscription, all due from `start`."""
    template_lines = list(golden["sub"].lines.all())
    subs = []
    for i in range(count):
        sub = Subscription.objects.create(number=f"SUB-C-{i}", customer=golden["customer"], plan=golden["plan"],
                                          status="active", start_date=start, next_invoice_date=start)
        SubscriptionLine.objects.bulk_create([
            SubscriptionLine(subscription=sub, product_id=l.product_id, variant_id=l.variant_id, quantity=l.quantity,
                             unit_price=l.unit_price, tax_group_id=l.tax_group_id)
            for l in template_lines
        ])
        subs.append(sub)
    return subs


def _in_threads(fn, n):
    errors = []

    def run():
        try:
            fn()
        except Exception as exc:  # surfaced by the assertion below
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=run) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors


def test_parallel_billing_runs_never_bill_twice(golden):
    _clone_subscriptions(golden, 5, date(2026, 1, 15))  # plus the golden one: 6 subscriptions x 3 periods
    _in_threads(lambda: services.run_billing(date(2026, 3, 20)), 3)

    assert Invoice.objects.count() == 18
    per_period = Invoice.objects.values_list("subscription_id", "period_start")
    assert len(set(per_period)) == 18


def test_discount_usage_limit_holds_under_concurrency(golden):
    Discount.objects.filter(pk=golden["discount"].pk).update(usage_limit=1)
    _clone_subscriptions(golden, 10, date(2026, 1, 15))
    golden["sub"].delete()  # keep exactly the 10 clones

    run = services.run_billing(date(2026, 1, 15))  # bills the 10 subscriptions in parallel workers

    assert run.created == 10 and run.failed == 0
    golden["discount"].refresh_from_db()
    assert golden["discount"].used_count == 1
    discounted = Invoice.objects.filter(discount_total__gt=Decimal("0"))
    assert discounted.count() == 1


def test_invoice_numbers_are_unique_and_gap_free(golden):
    _clone_subscriptions(golden, 7, date(2026, 1, 15))
    _in_threads(lambda: services.run_billing(date(2026, 2, 20)), 2)

    numbers = sorted(int(n.rsplit("-", 1)[1]) for n in Invoice.objects.values_list("number", flat=True))
    assert numbers == list(range(1, len(numbers) + 1))
    assert len(numbers) == 16  # 8 subscriptions x 2 periods
