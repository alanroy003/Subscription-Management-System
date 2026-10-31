"""Daily renewal reminders: python manage.py send_renewal_reminders [--date YYYY-MM-DD]. Safe to re-run."""
from datetime import date

from django.core.management.base import BaseCommand

from core.renewals import send_due_reminders


class Command(BaseCommand):
    help = "Email customers whose subscriptions expire in 30, 7 or 1 days (each reminder only once)."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=date.fromisoformat, default=None, help="pretend today is this date")

    def handle(self, *args, **opts):
        run = send_due_reminders(opts["date"])
        self.stdout.write(f"Renewal reminders: {len(run.sent)} sent, {run.skipped} already sent or not due")
        for r in run.sent:
            self.stdout.write(
                f"  {r['subscription']} ({r['customer']}): {r['days_before']} days before {r['expiry_date']}"
            )
