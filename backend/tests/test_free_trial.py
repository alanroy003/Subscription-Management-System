"""Free trial: a 0-rupee trial plan on the normal subscription engine, one per customer, convertible to paid."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from core import services
from core.models import AuditEvent, Customer, Invoice, Plan, Subscription
from core.trials import convert_trial, start_trial, trial_info

from .conftest import PASSWORD, client_for, make_user


@pytest.fixture
def trial_plan(golden):
    return Plan.objects.create(name="Free Trial (14 days)", product=golden["crm"], price=Decimal("0"),
                               billing_period="monthly", is_trial=True, trial_days=14, auto_close=True,
                               renewable=False)


def test_starting_a_trial_bills_a_settled_zero_invoice(golden, trial_plan):
    sub = start_trial(golden["customer"])
    today = date.today()
    assert sub.status == "active" and sub.plan == trial_plan
    assert sub.start_date == today and sub.expiry_date == today + timedelta(days=14)

    inv = Invoice.objects.get(subscription=sub)
    assert inv.total == Decimal("0.00") and inv.status == "paid" and not inv.is_overdue
    assert inv.period_end == today + timedelta(days=13)  # capped at the trial's last day, not a full month
    assert inv.number.startswith("INV-")
    assert AuditEvent.objects.filter(action="subscription.trial_started").count() == 1


def test_one_trial_per_customer(golden, trial_plan):
    start_trial(golden["customer"])
    with pytest.raises(services.DomainError, match="already had a free trial"):
        start_trial(golden["customer"])


def test_staff_cannot_bypass_the_one_trial_rule(golden, trial_plan, staff_user):
    start_trial(golden["customer"])
    c = client_for(staff_user)
    r = c.post("/api/subscriptions", {"customer": golden["customer"].id, "plan": trial_plan.id,
                                      "start_date": str(date.today()),
                                      "lines": [{"product": golden["crm"].id, "quantity": 1}]}, format="json")
    r = c.post(f"/api/subscriptions/{r.json()['id']}/transition", {"action": "confirm"}, format="json")
    assert r.status_code == 400 and "already had a free trial" in r.json()["detail"]


def test_trial_closes_itself_and_billing_never_charges(golden, trial_plan):
    sub = start_trial(golden["customer"])
    services.run_billing(date.today() + timedelta(days=20))
    sub.refresh_from_db()
    assert sub.status == "closed"
    assert list(Invoice.objects.filter(subscription=sub).values_list("total", flat=True)) == [Decimal("0.00")]


def test_convert_trial_to_paid_starts_when_the_trial_ends(golden, trial_plan):
    trial = start_trial(golden["customer"])
    paid = convert_trial(trial, golden["plan"].pk)
    trial.refresh_from_db()
    assert trial.converted_to == paid and trial.status == "active"  # the trial runs to its end
    assert paid.plan == golden["plan"] and paid.start_date == trial.expiry_date and paid.status == "confirmed"
    line = paid.lines.get()
    assert line.product == golden["crm"] and line.unit_price == golden["plan"].price  # paid plan price, not 0

    services.run_billing(trial.expiry_date)  # trial ends, the paid subscription starts and bills
    paid.refresh_from_db()
    trial.refresh_from_db()
    assert trial.status == "closed" and paid.status == "active"
    assert Invoice.objects.get(subscription=paid).total > 0
    with pytest.raises(services.DomainError, match="already converted"):
        convert_trial(trial, golden["plan"].pk)


def test_convert_after_the_trial_ended_starts_today(golden, trial_plan):
    trial = start_trial(golden["customer"])
    Subscription.objects.filter(pk=trial.pk).update(status="closed", expiry_date=date.today() - timedelta(days=3))
    paid = convert_trial(trial, golden["plan"].pk)
    assert paid.start_date == date.today() and paid.status == "active"
    assert Invoice.objects.filter(subscription=paid).count() == 1  # billed in advance on activation


def test_cannot_convert_to_another_trial_or_a_normal_subscription(golden, trial_plan):
    trial = start_trial(golden["customer"])
    with pytest.raises(services.DomainError, match="paid plan"):
        convert_trial(trial, trial_plan.pk)
    with pytest.raises(services.DomainError, match="Only a free trial"):
        convert_trial(golden["sub"], golden["plan"].pk)


def test_convert_is_not_a_plain_transition(golden, trial_plan, staff_user):
    trial = start_trial(golden["customer"])
    r = client_for(staff_user).post(f"/api/subscriptions/{trial.pk}/transition", {"action": "convert"}, format="json")
    assert r.status_code == 400


def test_signup_starts_the_trial_automatically(db, trial_plan, settings):
    r = APIClient().post("/api/auth/signup", {"email": "new@shop.in", "password": PASSWORD, "name": "New Shop"},
                         format="json")
    assert r.status_code == 201
    customer = Customer.objects.get(email="new@shop.in")
    assert Subscription.objects.get(customer=customer).plan == trial_plan


def test_signup_without_a_trial_plan_still_works(db):
    r = APIClient().post("/api/auth/signup", {"email": "x@shop.in", "password": PASSWORD}, format="json")
    assert r.status_code == 201 and not Subscription.objects.exists()


def test_portal_trial_flow(golden, trial_plan):
    owner = make_user("acme@example.com", User.Role.CUSTOMER)
    golden["customer"].user = owner
    golden["customer"].save()
    c = client_for(owner)

    info = c.get("/api/trial").json()
    assert info["eligible"] and info["plan"]["days"] == 14 and info["current"] is None
    assert golden["plan"].name in [p["name"] for p in info["paid_plans"]]
    assert trial_plan.name not in [p["name"] for p in info["paid_plans"]]

    trial = c.post("/api/trial/start").json()
    assert trial["is_trial"] and "convert" in trial["available_actions"]
    assert c.post("/api/trial/start").status_code == 400
    assert c.get("/api/trial").json()["current"]["days_left"] == 14

    paid = c.post(f"/api/subscriptions/{trial['id']}/convert", {"plan": golden["plan"].id}, format="json")
    assert paid.status_code == 201 and not paid.json()["is_trial"]
    assert c.get(f"/api/subscriptions/{trial['id']}").json()["converted_to_number"] == paid.json()["number"]


def test_customers_cannot_touch_other_trials(golden, trial_plan):
    trial = start_trial(golden["customer"])
    other = make_user("other@example.com", User.Role.CUSTOMER)
    Customer.objects.create(name="Other", email="other@example.com", user=other)
    r = client_for(other).post(f"/api/subscriptions/{trial.pk}/convert", {"plan": golden["plan"].id}, format="json")
    assert r.status_code == 404


def test_staff_start_a_trial_for_a_customer(golden, trial_plan, staff_user):
    c = client_for(staff_user)
    assert c.post("/api/trial/start", {}, format="json").status_code == 400  # must say which customer
    r = c.post("/api/trial/start", {"customer": golden["customer"].id}, format="json")
    assert r.status_code == 201 and trial_info(golden["customer"])["current"]["number"] == r.json()["number"]


def test_trial_plan_must_be_free(admin_user, golden):
    r = client_for(admin_user).post("/api/plans", {"name": "Bad trial", "product": golden["crm"].id, "price": "10",
                                                   "billing_period": "monthly", "is_trial": True}, format="json")
    assert r.status_code == 400 and "price" in r.json()
