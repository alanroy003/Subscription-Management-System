"""Renewal reminders: right day, never twice, catch-up sends only the most urgent, renewal starts a fresh set."""
from datetime import date, timedelta

import pytest

from core.models import AuditEvent, RenewalReminder, Subscription, SubscriptionEvent
from core.renewals import due_threshold, send_due_reminders

from .conftest import client_for, make_user

TODAY = date(2026, 6, 1)


@pytest.fixture
def mail(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail as django_mail

    return django_mail


@pytest.fixture
def expiring(golden):
    """The golden subscription, renewable, expiring 30 days after TODAY; plus an admin to copy."""
    make_user("boss@brightloop.test", "admin")
    sub = golden["sub"]
    sub.expiry_date = TODAY + timedelta(days=30)
    sub.save()
    golden["plan"].renewable = True
    golden["plan"].save()
    return sub


def test_threshold_windows():
    assert [due_threshold(d) for d in (45, 31, 30, 8, 7, 2, 1, 0, -1)] == [None, None, 30, 30, 7, 7, 1, 1, None]


def test_reminders_go_out_once_per_threshold(expiring, mail):
    run = send_due_reminders(TODAY)
    assert len(run.sent) == 1 and run.sent[0]["days_before"] == 30
    message = mail.outbox[0]
    assert message.to == ["acme@example.com"] and message.cc == ["boss@brightloop.test"]
    assert expiring.number in message.subject and "renew it here" in message.body
    assert f"/portal/subscriptions/{expiring.pk}" in message.body

    # Same day again, and the following days inside the 30-day window: nothing new.
    for offset in (0, 1, 10, 22):
        assert send_due_reminders(TODAY + timedelta(days=offset)).sent == []
    assert len(mail.outbox) == 1

    assert [r["days_before"] for r in send_due_reminders(TODAY + timedelta(days=23)).sent] == [7]
    assert [r["days_before"] for r in send_due_reminders(TODAY + timedelta(days=29)).sent] == [1]
    assert send_due_reminders(TODAY + timedelta(days=30)).sent == []  # 1-day reminder already covers expiry day
    assert sorted(RenewalReminder.objects.values_list("days_before", flat=True)) == [1, 7, 30]

    timeline = SubscriptionEvent.objects.filter(subscription=expiring, note__startswith="Renewal reminder")
    assert timeline.count() == 3
    assert AuditEvent.objects.filter(action="subscription.renewal_reminder").count() == 3


def test_missed_days_send_only_the_most_urgent(expiring, mail):
    run = send_due_reminders(TODAY + timedelta(days=24))  # job did not run for 24 days: 6 days left
    assert [r["days_before"] for r in run.sent] == [7] and len(mail.outbox) == 1
    assert send_due_reminders(TODAY + timedelta(days=25)).sent == []  # never goes back to the 30-day one


def test_renewal_starts_a_fresh_set(expiring, mail):
    send_due_reminders(TODAY + timedelta(days=29))  # 1-day reminder for the current expiry
    Subscription.objects.filter(pk=expiring.pk).update(expiry_date=TODAY + timedelta(days=60))
    run = send_due_reminders(TODAY + timedelta(days=30))  # new expiry is 30 days away
    assert [r["days_before"] for r in run.sent] == [30]


def test_only_live_subscriptions_with_an_expiry(expiring, mail):
    Subscription.objects.filter(pk=expiring.pk).update(status="closed")
    assert send_due_reminders(TODAY).sent == []
    Subscription.objects.filter(pk=expiring.pk).update(status="paused")
    assert len(send_due_reminders(TODAY).sent) == 1  # paused customers still need to decide
    Subscription.objects.filter(pk=expiring.pk).update(expiry_date=None, status="active")
    assert send_due_reminders(TODAY + timedelta(days=29)).sent == []


def test_customer_without_email_notifies_the_team(expiring, golden, mail):
    golden["customer"].email = ""
    golden["customer"].save()
    send_due_reminders(TODAY)
    assert mail.outbox[0].to == ["boss@brightloop.test"] and mail.outbox[0].cc == []


def test_non_renewable_plan_says_so(expiring, golden, mail):
    golden["plan"].renewable = False
    golden["plan"].save()
    send_due_reminders(TODAY)
    assert "does not renew automatically" in mail.outbox[0].body


def test_failed_email_is_retried_next_run(expiring, settings, monkeypatch):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core.mail import EmailMessage

    def boom(self, fail_silently=False):
        raise OSError("SMTP down")

    monkeypatch.setattr(EmailMessage, "send", boom)
    with pytest.raises(OSError):
        send_due_reminders(TODAY)
    assert not RenewalReminder.objects.exists()  # rolled back, so the next run sends it
    monkeypatch.undo()
    assert len(send_due_reminders(TODAY).sent) == 1


def test_renewals_api(expiring, staff_user, mail):
    sub = Subscription.objects.get(pk=expiring.pk)
    sub.expiry_date = date.today() + timedelta(days=20)
    sub.save()
    staff = client_for(staff_user)
    rows = staff.get("/api/renewals?days=30").json()["results"]
    assert [r["number"] for r in rows] == [sub.number] and rows[0]["reminders_sent"] == []
    assert rows[0]["days_left"] == 20

    sent = staff.post("/api/renewals/send-reminders").json()
    assert sent["sent"] == 1 and sent["reminders"][0]["days_before"] == 30
    assert staff.get("/api/renewals").json()["results"][0]["reminders_sent"] == [30]
    assert staff.post("/api/renewals/send-reminders").json()["sent"] == 0


def test_customers_cannot_use_the_renewals_api(golden):
    customer = make_user("c@x.com", "customer")
    assert client_for(customer).get("/api/renewals").status_code == 403
    assert client_for(customer).post("/api/renewals/send-reminders").status_code == 403
