"""Billing day: python manage.py run_billing [--date YYYY-MM-DD] [--dry-run]. Safe to re-run (idempotent)."""
from datetime import date

from django.core.management.base import BaseCommand

from core.services import run_billing


class Command(BaseCommand):
    help = "Create invoices for every subscription that is due."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=date.fromisoformat, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        run = run_billing(opts["date"], opts["dry_run"])
        label = "DRY RUN " if run.dry_run else ""
        self.stdout.write(f"{label}{run.run_date}: created {run.created}, failed {run.failed}")
        for item in run.items:
            if item["status"] == "failed":
                self.stderr.write(f"  {item['subscription_number']}: {item['error']}")
