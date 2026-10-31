"""Audit log: every sensitive action leaves exactly one event, secrets never appear, admins only, append-only.
API docs: Swagger, ReDoc and the schema are served and cover the versioned API."""
from datetime import date

import pytest
from django.db import IntegrityError, connection, transaction
from rest_framework.test import APIClient

from accounts.models import User
from core import services
from core.models import AuditEvent, Invoice

from .conftest import PASSWORD, client_for, make_user


def actions() -> list[str]:
    return list(AuditEvent.objects.order_by("id").values_list("action", flat=True))


def test_auth_events_and_no_secrets(db):
    make_user("a@x.com", User.Role.STAFF)
    c = APIClient(REMOTE_ADDR="10.0.0.7")
    c.post("/api/auth/login", {"email": "a@x.com", "password": "nope"}, format="json")  # pragma: allowlist secret
    token = c.post("/api/auth/login", {"email": "a@x.com", "password": PASSWORD}, format="json").json()["token"]
    c.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    c.post("/api/auth/logout")
    c.credentials()  # the app drops its token after signing out
    c.post("/api/auth/signup", {"email": "new@x.com", "password": PASSWORD, "name": "New"}, format="json")

    assert actions() == ["auth.login_failed", "auth.login", "auth.logout", "auth.signup"]
    failed = AuditEvent.objects.get(action="auth.login_failed")
    assert failed.object_ref == "a@x.com" and failed.actor is None and failed.ip == "10.0.0.7"
    ok = AuditEvent.objects.get(action="auth.login")
    assert ok.actor_label == "a@x.com" and ok.via == "web"
    dump = str(list(AuditEvent.objects.values_list("changes", flat=True)))
    assert PASSWORD not in dump and "pbkdf2" not in dump


def test_admin_changes_are_logged_with_field_diffs(admin_user, golden):
    admin = client_for(admin_user)
    admin.post("/api/users", {"email": "s2@x.com", "name": "S2", "password": PASSWORD, "role": "staff"}, format="json")
    admin.patch(f"/api/discounts/{golden['discount'].pk}", {"value": "12.50"}, format="json")
    admin.post("/api/tax-groups", {"name": "GST 5%", "rate": "5", "mode": "gst"}, format="json")

    assert actions() == ["user.created", "discount.updated", "taxgroup.created"]
    created = AuditEvent.objects.get(action="user.created")
    assert "password" not in created.changes["after"] and created.actor == admin_user
    assert AuditEvent.objects.get(action="discount.updated").changes == {"value": ["10.00", "12.50"]}


def test_billing_invoice_and_payment_events(admin_user, golden):
    services.run_billing(date(2026, 1, 15), user=admin_user)
    inv = services.confirm_invoice(Invoice.objects.get())
    services.record_payment(inv, "upi", inv.total, date(2026, 1, 20), "", admin_user)
    services.run_billing(date(2026, 1, 15), dry_run=True)

    assert actions() == ["invoice.created", "billing.run", "invoice.confirmed", "payment.recorded", "billing.dry_run"]
    paid = AuditEvent.objects.get(action="payment.recorded")
    assert paid.object_ref == inv.number and paid.changes["amount"] == str(inv.total) and paid.actor == admin_user
    assert AuditEvent.objects.get(action="billing.dry_run").via == "system"


def test_rolled_back_change_leaves_no_event(golden):
    services.run_billing(date(2026, 1, 15))
    inv = services.confirm_invoice(Invoice.objects.get())
    before = AuditEvent.objects.count()
    with pytest.raises(services.DomainError):
        services.record_payment(inv, "upi", inv.total + 1, date(2026, 1, 20), "", None)
    assert AuditEvent.objects.count() == before


def test_api_key_requests_are_attributed_to_the_key(admin_user, golden):
    raw = client_for(admin_user).post("/api/api-keys", {"name": "ERP", "scopes": ["read", "write"]}, format="json")
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw.json()["key"])
    c.post("/api/v1/customers", {"name": "Via API", "email": "api@example.com"}, format="json")
    event = AuditEvent.objects.get(action="customer.created")
    assert event.via == "api_key" and event.api_key_prefix == raw.json()["prefix"] and event.actor == admin_user


def test_audit_api_is_admin_only_and_filterable(admin_user, staff_user, golden):
    client_for(admin_user).post("/api/tax-groups", {"name": "GST 5%", "rate": "5", "mode": "gst"}, format="json")
    assert client_for(staff_user).get("/api/audit-events").status_code == 403
    r = client_for(admin_user).get("/api/audit-events?action=taxgroup.")
    assert r.status_code == 200 and r.json()["count"] == 1
    assert client_for(admin_user).get("/api/audit-events?action=invoice.").json()["count"] == 0


@pytest.mark.skipif(connection.vendor != "postgresql", reason="trigger is Postgres-only")
def test_audit_log_is_append_only(admin_user):
    from core.audit import record
    event = record("test.event", ref="x", actor=admin_user)
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEvent.objects.filter(pk=event.pk).update(action="tampered")
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEvent.objects.filter(pk=event.pk).delete()
    AuditEvent.objects.filter(pk=event.pk).update(published_at="2026-01-01T00:00:00Z")  # outbox marker is allowed


def test_api_docs_are_served(db):
    c = APIClient()
    assert c.get("/api/docs").status_code == 200
    assert c.get("/api/redoc").status_code == 200
    schema = c.get("/api/schema", HTTP_ACCEPT="application/json").json()
    assert all(path.startswith("/api/v1/") for path in schema["paths"])
    assert "/api/v1/auth/login" in schema["paths"] and "/api/v1/audit-events" in schema["paths"]
    login = schema["paths"]["/api/v1/auth/login"]["post"]
    assert login["tags"] == ["auth"] and "requestBody" in login
    assert {"tokenAuth", "ApiKeyAuth"} <= set(schema["components"]["securitySchemes"])
