import re
from pathlib import Path

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from accounts.models import User
from core.models import Customer, Subscription

from .conftest import PASSWORD, client_for, make_user


@pytest.mark.parametrize("bad", ["Short#1a", "alllower#123", "ALLUPPER#123", "NoSpecial123"])
def test_password_policy_rejected(db, bad):
    r = APIClient().post("/api/auth/signup", {"email": "x@example.com", "password": bad}, format="json")
    assert r.status_code == 400 and "password" in r.json()


def test_signup_creates_customer_and_email_is_unique(db):
    c = APIClient()
    r = c.post("/api/auth/signup", {"email": "New@Example.com", "password": PASSWORD, "name": "New Co"}, format="json")
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "customer"
    assert Customer.objects.get(email="new@example.com").user.email == "new@example.com"
    r = c.post("/api/auth/signup", {"email": "new@example.com", "password": PASSWORD}, format="json")
    assert r.status_code == 400 and "email" in r.json()


def test_public_signup_cannot_create_staff(db):
    r = APIClient().post("/api/auth/signup", {"email": "e@x.com", "password": PASSWORD, "role": "admin"}, format="json")
    assert r.json()["user"]["role"] == "customer"


def test_login_and_me(db):
    make_user("a@x.com", User.Role.STAFF)
    c = APIClient()
    r = c.post("/api/auth/login", {"email": "a@x.com", "password": PASSWORD}, format="json")
    assert r.status_code == 200
    c.credentials(HTTP_AUTHORIZATION=f"Token {r.json()['token']}")
    assert c.get("/api/auth/me").json()["role"] == "staff"
    assert APIClient().post("/api/auth/login", {"email": "a@x.com", "password": "wrong"}, format="json").status_code == 400


def test_password_reset_flow(db, tmp_path, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail
    make_user("r@x.com", User.Role.CUSTOMER)
    c = APIClient()
    assert c.post("/api/auth/password-reset", {"email": "r@x.com"}, format="json").status_code == 200
    assert c.post("/api/auth/password-reset", {"email": "nobody@x.com"}, format="json").status_code == 200
    assert len(mail.outbox) == 1
    uid, token = re.search(r"uid=([^&]+)&token=(\S+)", mail.outbox[0].body).groups()
    r = c.post("/api/auth/password-reset/confirm", {"uid": uid, "token": token, "password": "weak"}, format="json")
    assert r.status_code == 400
    r = c.post("/api/auth/password-reset/confirm", {"uid": uid, "token": token, "password": "Newer#Pass22"}, format="json")
    assert r.status_code == 200
    assert c.post("/api/auth/login", {"email": "r@x.com", "password": "Newer#Pass22"}, format="json").status_code == 200


def test_only_admin_adds_staff(admin_user, staff_user):
    body = {"email": "s2@x.com", "name": "S2", "password": PASSWORD, "role": "staff"}
    assert client_for(staff_user).post("/api/users", body, format="json").status_code == 403
    assert client_for(admin_user).post("/api/users", body, format="json").status_code == 201
    bad = dict(body, email="c@x.com", role="customer")
    assert client_for(admin_user).post("/api/users", bad, format="json").status_code == 400


def test_staff_reads_catalog_but_cannot_write(staff_user, admin_user):
    s = client_for(staff_user)
    assert s.get("/api/products").status_code == 200
    body = {"name": "P", "sales_price": "10", "cost_price": "5"}
    assert s.post("/api/products", body, format="json").status_code == 403
    assert s.post("/api/discounts", {"name": "D", "kind": "fixed", "value": "5"}, format="json").status_code == 403
    assert client_for(admin_user).post("/api/products", body, format="json").status_code == 201


def test_customer_isolation(golden):
    owner = make_user("acme@example.com", User.Role.CUSTOMER)
    golden["customer"].user = owner
    golden["customer"].save()
    other = make_user("other@example.com", User.Role.CUSTOMER)
    Customer.objects.create(name="Other", email="other@example.com", user=other)
    sub = golden["sub"]
    from core import services
    from datetime import date
    services.run_billing(date(2026, 1, 15))
    from core.models import Invoice
    inv = services.confirm_invoice(Invoice.objects.get())

    mine, theirs = client_for(owner), client_for(other)
    assert mine.get(f"/api/subscriptions/{sub.id}").status_code == 200
    assert theirs.get(f"/api/subscriptions/{sub.id}").status_code == 404
    assert theirs.get("/api/subscriptions").json()["count"] == 0
    assert mine.get(f"/api/invoices/{inv.id}").status_code == 200
    assert theirs.get(f"/api/invoices/{inv.id}").status_code == 404
    assert theirs.post(f"/api/subscriptions/{sub.id}/transition", {"action": "pause"}, format="json").status_code == 404
    # Customers cannot reach team or admin APIs.
    for url in ("/api/users", "/api/products", "/api/reports/summary", "/api/billing/runs"):
        assert mine.get(url).status_code == 403, url
    assert mine.post(f"/api/invoices/{inv.id}/confirm").status_code == 403
    assert mine.post("/api/payments", {"invoice": inv.id, "method": "cash", "amount": "1", "date": "2026-01-16"},
                     format="json").status_code == 403
    # Owner can pause because the plan allows it.
    r = mine.post(f"/api/subscriptions/{sub.id}/transition", {"action": "pause"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "paused"
