from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from core.models import Customer, Discount, Plan, Product, ProductVariant, Subscription, SubscriptionLine, TaxGroup

PASSWORD = "Strong#Pass1"  # pragma: allowlist secret (test value)


@pytest.fixture
def api():
    return APIClient()


def make_user(email, role, **extra):
    return User.objects.create_user(email, PASSWORD, role=role, name=email.split("@")[0], **extra)


@pytest.fixture
def admin_user(db):
    return make_user("admin@brightloop.test", User.Role.ADMIN)


@pytest.fixture
def staff_user(db):
    return make_user("staff@brightloop.test", User.Role.STAFF)


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def golden(db):
    """The worked example from docs/01-planning/mvp-plan.md (golden billing test)."""
    gst = TaxGroup.objects.create(name="GST 18%", rate=Decimal("18"), mode="gst")
    crm = Product.objects.create(name="Brightloop CRM", type="software", sales_price=Decimal("1000"),
                                 cost_price=Decimal("300"), tax_group=gst)
    odoo = ProductVariant.objects.create(product=crm, attribute="Brand", value="Odoo", price_extra=Decimal("560"))
    support = Product.objects.create(name="Priority support", type="service", sales_price=Decimal("500"), tax_group=gst)
    plan = Plan.objects.create(name="CRM Monthly", product=crm, price=Decimal("1200"), billing_period="monthly",
                               min_quantity=1, pausable=True)
    volume = Discount.objects.create(name="Volume 10%", kind="percent", value=Decimal("10"), min_quantity=5,
                                     usage_limit=2, scope="products")
    volume.products.add(crm)
    customer = Customer.objects.create(name="Acme Traders", email="acme@example.com", state="Gujarat")
    sub = Subscription.objects.create(number="SUB-T-1", customer=customer, plan=plan, status="active",
                                      start_date=date(2026, 1, 15), next_invoice_date=date(2026, 1, 15),
                                      payment_term_days=15)
    SubscriptionLine.objects.create(subscription=sub, product=crm, variant=odoo, quantity=5,
                                    unit_price=Decimal("1760"), tax_group=gst)
    SubscriptionLine.objects.create(subscription=sub, product=support, quantity=1, unit_price=Decimal("500"),
                                    tax_group=gst)
    return {"sub": sub, "customer": customer, "discount": volume, "plan": plan, "crm": crm, "odoo": odoo, "gst": gst}
