"""Renewal reminders: email the customer (copying the admins) 30, 7 and 1 day before a subscription expires.

Run daily after billing (scheduler, `manage.py send_renewal_reminders`, or "Send reminders now"). Each reminder is
recorded once per (subscription, expiry date, threshold), so re-running never repeats one. If the job missed some
days, only the most urgent reminder that is due is sent (no burst of three emails). Renewing sets a new expiry date,
which starts a fresh set of reminders.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import IntegrityError, transaction

from . import audit
from .models import RenewalReminder, Subscription, SubscriptionEvent
from .parallel import map_parallel

WINDOW_DAYS = max(RenewalReminder.THRESHOLDS)
S = Subscription.Status


def due_threshold(days_left: int) -> int | None:
    """The reminder that applies `days_left` days before expiry: 30 for 8-30 days, 7 for 2-7, 1 for 0-1."""
    if days_left < 0:
        return None
    for threshold in sorted(RenewalReminder.THRESHOLDS):
        if days_left <= threshold:
            return threshold
    return None


def upcoming(today: date | None = None, days: int = WINDOW_DAYS):
    """Active or paused subscriptions expiring within `days` days, soonest first."""
    today = today or date.today()
    return (
        Subscription.objects.filter(
            status__in=[S.ACTIVE, S.PAUSED], expiry_date__range=(today, today + timedelta(days))
        )
        .select_related("customer", "plan")
        .order_by("expiry_date", "id")
    )


@dataclass
class ReminderRun:
    sent: list[dict] = field(default_factory=list)
    skipped: int = 0

    def as_dict(self) -> dict:
        return {"sent": len(self.sent), "skipped": self.skipped, "reminders": self.sent}


def _admin_emails() -> list[str]:
    from accounts.models import User

    return list(User.objects.filter(role=User.Role.ADMIN, is_active=True).values_list("email", flat=True))


def _message(sub: Subscription, threshold: int, days_left: int) -> tuple[str, str]:
    company = settings.COMPANY["name"]
    when = "tomorrow" if days_left == 1 else ("today" if days_left == 0 else f"in {days_left} days")
    subject = f"Your {sub.plan.name} subscription {sub.number} ends {when}"
    link = f"{settings.FRONTEND_URL}/portal/subscriptions/{sub.pk}"
    if sub.plan.renewable:
        action = f"To keep it running without interruption, renew it here: {link}"
    else:
        action = f"This plan does not renew automatically. Reply to this email to discuss a new plan. Details: {link}"
    body = (
        f"Dear {sub.customer.name},\n\n"
        f"Your subscription {sub.number} ({sub.plan.name}) expires on {sub.expiry_date:%d %b %Y}, {when}.\n"
        f"{action}\n\n{company}"
    )
    return subject, body


def _send_one(sub: Subscription, threshold: int, days_left: int, admins: list[str], user) -> dict | None:
    """Record and send one reminder in its own transaction. None if there is nobody to send to or it already exists."""
    customer_email = (sub.customer.email or "").strip()
    to = [customer_email] if customer_email else admins
    cc = admins if customer_email else []
    if not to:
        return None
    subject, body = _message(sub, threshold, days_left)
    try:
        with transaction.atomic():
            reminder = RenewalReminder.objects.create(
                subscription=sub, expiry_date=sub.expiry_date, days_before=threshold, sent_to=to + cc
            )
            SubscriptionEvent.objects.create(
                subscription=sub, from_status=sub.status, to_status=sub.status, user=user,
                note=f"Renewal reminder sent ({threshold} day{'s' if threshold != 1 else ''} before expiry)",
            )
            audit.record("subscription.renewal_reminder", sub, actor=user,
                         changes={"days_before": threshold, "expiry_date": sub.expiry_date, "to": to + cc})
            # Sent last: if the email fails, the record rolls back and the next run tries again.
            EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, to, cc=cc).send(fail_silently=False)
    except IntegrityError:  # a concurrent run recorded it first
        return None
    return {"subscription": sub.number, "customer": sub.customer.name, "expiry_date": str(sub.expiry_date),
            "days_before": threshold, "to": to + cc, "reminder_id": reminder.pk}


def send_due_reminders(today: date | None = None, user=None) -> ReminderRun:
    today = today or date.today()
    run = ReminderRun()
    admins = _admin_emails()
    subs = list(upcoming(today))
    # Thresholds already sent for each subscription's current expiry date, in one query.
    already: dict[tuple, set[int]] = {}
    for sub_id, expiry, days_before in RenewalReminder.objects.filter(subscription__in=subs).values_list(
        "subscription_id", "expiry_date", "days_before"
    ):
        already.setdefault((sub_id, expiry), set()).add(days_before)

    due = []
    for sub in subs:
        days_left = (sub.expiry_date - today).days
        threshold = due_threshold(days_left)
        sent = already.get((sub.pk, sub.expiry_date), set())
        if threshold is None or any(t <= threshold for t in sent):
            run.skipped += 1  # already reminded at this or a more urgent threshold for this expiry date
            continue
        due.append((sub, threshold, days_left))

    # Each reminder is independent, so they go out in parallel (the database is a long round trip away).
    results = map_parallel(lambda item: _send_one(*item, admins, user), due)
    for result in results:
        if result is None:
            run.skipped += 1
        else:
            run.sent.append(result)
    return run
