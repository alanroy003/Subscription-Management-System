"""Time the main API endpoints in-process against the configured database.

Usage (from backend/): ../backend/.venv/Scripts/python ../scripts/perf_check.py [--rounds 5]
Pass criterion: p95 of every endpoint under 2000 ms (page budget); target under 500 ms where the network allows.
"""
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()
from django.test.utils import CaptureQueriesContext  # noqa: E402
from django.db import connection  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from accounts.models import User  # noqa: E402
from core.models import Invoice, Subscription  # noqa: E402

rounds = int(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else 5
admin = User.objects.filter(role="admin").first()
customer = User.objects.filter(email="customer@brightloop.test").first()
sub = Subscription.objects.order_by("id").first()
inv = Invoice.objects.order_by("-id").first()

checks = [
    (admin, "/api/reports/summary"),
    (admin, "/api/subscriptions"),
    (admin, "/api/subscriptions?status=active&search=CRM"),
    (admin, f"/api/subscriptions/{sub.id}"),
    (admin, "/api/invoices"),
    (admin, "/api/invoices?overdue=true"),
    (admin, f"/api/invoices/{inv.id}"),
    (admin, "/api/payments"),
    (admin, "/api/customers"),
    (admin, "/api/products"),
    (customer, "/api/subscriptions"),
    (customer, "/api/invoices"),
]
ALLOWED_HOSTS_OK = os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver")
worst = 0.0
print(f"{'endpoint':55} {'queries':>7} {'p50 ms':>7} {'p95 ms':>7}")
for user, url in checks:
    client = APIClient(SERVER_NAME="localhost")
    client.force_authenticate(user)
    times = []
    for _ in range(rounds):
        with CaptureQueriesContext(connection) as ctx:
            t = time.perf_counter()
            r = client.get(url)
            times.append((time.perf_counter() - t) * 1000)
        assert r.status_code == 200, (url, r.status_code)
    times.sort()
    p95 = times[min(len(times) - 1, int(round(0.95 * (len(times) - 1))))]
    worst = max(worst, p95)
    print(f"{url[:55]:55} {len(ctx.captured_queries):>7} {statistics.median(times):>7.0f} {p95:>7.0f}")
print(f"\nworst p95: {worst:.0f} ms -> {'PASS' if worst < 2000 else 'FAIL'} (budget 2000 ms)")
