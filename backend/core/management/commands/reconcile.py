"""Nightly data check: python manage.py reconcile [--no-email]. Exits with code 1 when issues are found."""
import sys

from django.core.management.base import BaseCommand

from core.integrity import run_check


class Command(BaseCommand):
    help = "Check that invoice totals, payments, discount usage and billing schedules still add up."

    def add_arguments(self, parser):
        parser.add_argument("--no-email", action="store_true", help="do not email admins about issues")

    def handle(self, *args, **opts):
        check = run_check(notify=not opts["no_email"])
        if not check.issue_count:
            self.stdout.write(self.style.SUCCESS(f"All good: {check.counts}"))
            return
        self.stderr.write(f"{check.issue_count} issue(s) found:")
        for issue in check.issues[:50]:
            self.stderr.write(f"  [{issue['check']}] {issue['ref']}: {issue['detail']}")
        sys.exit(1)
