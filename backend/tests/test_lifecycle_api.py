from datetime import date, timedelta
from decimal import Decimal

from core.models import Invoice, QuotationTemplate, QuotationTemplateLine

from .conftest import client_for


def test_quote_to_active_subscription_bills_first_invoice(golden, staff_user):
    tpl = QuotationTemplate.objects.create(name="CRM starter", plan=golden["plan"], validity_days=10)
    QuotationTemplateLine.objects.create(template=tpl, product=golden["crm"], variant=golden["odoo"], quantity=2)
    c = client_for(staff_user)
    r = c.post("/api/subscriptions/from-template",
               {"template": tpl.id, "customer": golden["customer"].id, "start_date": str(date.today())}, format="json")
    assert r.status_code == 201, r.json()
    sub = r.json()
    assert sub["status"] == "quotation" and sub["number"].startswith("SUB-")
    assert sub["quotation_valid_until"] == str(date.today() + timedelta(days=10))
    assert sub["lines"][0]["unit_price"] == "1760.00"

    r = c.post(f"/api/subscriptions/{sub['id']}/transition", {"action": "activate"}, format="json")
    assert r.status_code == 400  # quotation cannot jump to active

    r = c.post(f"/api/subscriptions/{sub['id']}/transition", {"action": "confirm"}, format="json")
    body = r.json()
    assert body["status"] == "active"
    assert [e["to_status"] for e in body["events"]] == ["draft", "quotation", "confirmed", "active"]
    inv = Invoice.objects.get(subscription_id=sub["id"])
    assert inv.total == Decimal("4153.60")  # 2 x 1760 = 3520 + 18% GST; below discount min quantity

    # Lines are locked after confirmation.
    assert c.patch(f"/api/subscriptions/{sub['id']}", {"notes": "x"}, format="json").status_code == 400


def test_min_quantity_and_availability_enforced(golden, staff_user):
    plan = golden["plan"]
    plan.min_quantity = 10
    plan.available_to = date(2020, 1, 1)
    plan.save()
    c = client_for(staff_user)
    r = c.post(
        "/api/subscriptions",
        {
            "customer": golden["customer"].id,
            "plan": plan.id,
            "start_date": str(date.today()),
            "lines": [{"product": golden["crm"].id, "quantity": 2}],
        },
        format="json",
    )
    assert r.status_code == 201
    r = c.post(f"/api/subscriptions/{r.json()['id']}/transition", {"action": "confirm"}, format="json")
    assert r.status_code == 400 and "not available" in r.json()["detail"]


def test_invoice_actions_and_overdue_filter(golden, staff_user, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from core import services
    services.run_billing(date(2026, 1, 15))
    inv = Invoice.objects.get()
    c = client_for(staff_user)
    r = c.post(f"/api/invoices/{inv.id}/send")
    assert r.status_code == 200 and r.json()["status"] == "confirmed" and r.json()["sent_at"]
    assert c.get("/api/invoices?overdue=true").json()["count"] == 1
    r = c.post("/api/payments", {"invoice": inv.id, "method": "upi", "amount": "9935.60", "date": "2026-01-20"},
               format="json")
    assert r.status_code == 201
    assert c.get(f"/api/invoices/{inv.id}").json()["status"] == "paid"
    assert c.get("/api/invoices?overdue=true").json()["count"] == 0
    assert c.get("/api/reports/summary").status_code == 200
