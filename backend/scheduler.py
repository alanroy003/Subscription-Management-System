"""Scheduler loop for Docker: runs the billing day, then the data reconciliation, daily at BILLING_HOUR and on start-up.

Billing is idempotent and catches up missed days, so restarts or double runs never bill twice.
"""
import os
import subprocess
import time
from datetime import datetime, timedelta

HOUR = int(os.environ.get("BILLING_HOUR", "2"))


def run():
    subprocess.run(["python", "manage.py", "run_billing"], check=False)
    subprocess.run(["python", "manage.py", "send_renewal_reminders"], check=False)
    subprocess.run(["python", "manage.py", "reconcile"], check=False)  # emails admins if anything drifted


run()
while True:
    now = datetime.now()
    nxt = now.replace(hour=HOUR, minute=0, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    time.sleep((nxt - now).total_seconds())
    run()
