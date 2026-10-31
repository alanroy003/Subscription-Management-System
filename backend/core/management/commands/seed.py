"""Demo and performance data.

    python manage.py seed --reset              # demo set: ~60 customers, ~150 subscriptions, 14 months of history
    python manage.py seed --reset --subs 10000 # performance set (~100k invoices)

Demo logins (local test values only): admin@brightloop.test, staff@brightloop.test, customer@brightloop.test,
password from DEMO_PASSWORD in .env or the default below.
"""
import os
import random
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction

from accounts.models import User
from core.models import (BillingRun, Customer, Discount, Invoice, InvoiceLine, Payment, Plan, Product, ProductVariant,
                         QuotationTemplate, QuotationTemplateLine, Sequence, Subscription, SubscriptionEvent,
                         SubscriptionLine, TaxGroup)
from core.money import next_period_start, q
from core.pricing import LineInput, default_unit_price, price_lines

DEFAULT_DEMO_PASSWORD = "Demo#Pass2026"
D = Decimal

COMPANIES = ["Acme Traders", "Sunrise Textiles", "Patel Agro Foods", "Mehta Logistics", "Kaveri Pharma", "Blue Lotus Cafe",
             "Shakti Steel", "Nimbus Tech", "Ganga Handlooms", "Orbit Electronics", "Saffron Retail", "Indus Motors",
             "Coral Clinics", "Vertex Builders", "Monsoon Media", "Tulsi Organics", "Aravali Granite", "Peacock Prints",
             "Deccan Dairies", "Himalaya Travels", "Lotus Learning", "Narmada Chemicals", "Pinnacle Finance", "Ruby Jewels",
             "Sahyadri Farms", "Trident Packaging", "Unity Hospitals", "Vista Interiors", "Zenith Solar", "Amber Apparel",
             "Banyan Books", "Cobalt Systems", "Dhruv Diagnostics", "Emerald Exports", "Falcon Security", "Garnet Hotels",
             "Horizon Realty", "Ivory Spa", "Jasmine Foods", "Kestrel Aviation", "Lakshmi Silks", "Marigold Events",
             "Neem Naturals", "Opal Optics", "Prism Analytics", "Quartz Labs", "Raga Music", "Sapphire Salons",
             "Teak Furniture", "Umbrella Insurance", "Vanilla Bakers", "Willow Wellness", "Yamuna Water Tech",
             "Zest Kitchens", "Aqua Pure", "Bharat Hardware", "Chakra Yoga", "Diya Lighting", "Eagle Couriers", "Fern Studio"]
STATES = ["Gujarat"] * 5 + ["Maharashtra", "Karnataka", "Tamil Nadu", "Delhi", "Rajasthan", "Telangana", "West Bengal"]


class Command(BaseCommand):
    help = "Seed demo data (use --reset to wipe business data first)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--subs", type=int, default=150)
        parser.add_argument("--customers", type=int, default=0)

    def handle(self, *args, **opts):
        self.rng = random.Random(42)
        self.today = date.today()
        if opts["reset"]:
            self.reset()
        with transaction.atomic():
            self.users()
            catalog = self.catalog()
            customers = self.customers(opts["customers"] or max(60, opts["subs"] // 3))
            self.subscriptions(catalog, customers, opts["subs"])
        self.stdout.write(self.style.SUCCESS("Seed complete."))

    # ------------------------------------------------------------------ setup
    def reset(self):
        models = [Payment, InvoiceLine, Invoice, SubscriptionEvent, SubscriptionLine, Subscription, QuotationTemplateLine,
                  QuotationTemplate, Discount.products.through, Discount, Plan, ProductVariant, Product, TaxGroup,
                  Customer, BillingRun, Sequence]
        if connection.vendor == "postgresql":
            tables = ", ".join(connection.ops.quote_name(m._meta.db_table) for m in models)
            with connection.cursor() as cur:
                cur.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
        else:
            for m in models:
                m.objects.all().delete()
        User.objects.filter(email__endswith="@brightloop.test").delete()
        User.objects.filter(role=User.Role.CUSTOMER).delete()
        self.stdout.write("Business data reset.")

    def users(self):
        pw = os.environ.get("DEMO_PASSWORD", DEFAULT_DEMO_PASSWORD)
        for email, role, name in [("admin@brightloop.test", User.Role.ADMIN, "Asha Admin"),
                                  ("staff@brightloop.test", User.Role.STAFF, "Sam Staff"),
                                  ("customer@brightloop.test", User.Role.CUSTOMER, "Acme Traders")]:
            if not User.objects.filter(email=email).exists():
                User.objects.create_user(email, pw, role=role, name=name, is_staff=role == User.Role.ADMIN,
                                         is_superuser=role == User.Role.ADMIN)

    def catalog(self):
        gst = {r: TaxGroup.objects.create(name=f"GST {r}%", rate=D(r), mode="gst") for r in (5, 12, 18, 28)}
        TaxGroup.objects.create(name="Export (zero rated)", rate=D(0), mode="simple")
        g18 = gst[18]
        crm = Product.objects.create(name="Brightloop CRM", type="software", sales_price=D(1000), cost_price=D(250),
                                     tax_group=g18, notes="Per-seat CRM licence")
        odoo = ProductVariant.objects.create(product=crm, attribute="Brand", value="Odoo", price_extra=D(560))
        ProductVariant.objects.create(product=crm, attribute="Brand", value="Standard", price_extra=D(0))
        acc = Product.objects.create(name="Brightloop Accounting", type="software", sales_price=D(1500), cost_price=D(400), tax_group=g18)
        hr = Product.objects.create(name="Brightloop HR Suite", type="software", sales_price=D(800), cost_price=D(200), tax_group=g18)
        storage = Product.objects.create(name="Extra storage 100 GB", type="service", sales_price=D(200), cost_price=D(40), tax_group=g18)
        support = Product.objects.create(name="Priority support", type="service", sales_price=D(500), cost_price=D(150), tax_group=g18)
        Product.objects.create(name="Onboarding workshop", type="service", sales_price=D(2500), cost_price=D(900), tax_group=g18)
        analytics = Product.objects.create(name="Analytics add-on", type="software", sales_price=D(400), cost_price=D(60), tax_group=g18)
        Product.objects.create(name="Barcode scanner", type="goods", sales_price=D(3200), cost_price=D(2100), tax_group=gst[12])

        plans = {
            "crm_m": Plan.objects.create(name="CRM Monthly", product=crm, price=D(1200), billing_period="monthly",
                                         pausable=True, closable=True, renewable=True),
            "crm_y": Plan.objects.create(name="CRM Yearly", product=crm, price=D(12000), billing_period="yearly",
                                         min_quantity=5, pausable=False, closable=False, renewable=True),
            "acc_m": Plan.objects.create(name="Accounting Monthly", product=acc, price=D(1500), billing_period="monthly",
                                         pausable=True, renewable=True),
            "hr_w": Plan.objects.create(name="HR Weekly", product=hr, price=D(250), billing_period="weekly",
                                        auto_close=True, renewable=False),
            "sandbox": Plan.objects.create(name="Sandbox Daily", product=crm, price=D(60), billing_period="daily",
                                           auto_close=True, renewable=False, closable=True),
            "legacy": Plan.objects.create(name="Legacy CRM 2024", product=crm, price=D(900), billing_period="monthly",
                                          available_to=date(2024, 12, 31)),
        }
        volume = Discount.objects.create(name="Volume 10% (5+ seats)", kind="percent", value=D(10), min_quantity=5,
                                         usage_limit=5000, scope="products")
        volume.products.add(crm, acc)
        Discount.objects.create(name="Welcome ₹500", kind="fixed", value=D(500), min_amount=D(5000), usage_limit=40,
                                scope="all", start_date=self.today - timedelta(days=400))
        Discount.objects.create(name="Diwali 15%", kind="percent", value=D(15), scope="all",
                                start_date=date(2025, 10, 15), end_date=date(2025, 11, 5))

        tpl = QuotationTemplate.objects.create(name="CRM Starter (Odoo)", plan=plans["crm_m"], validity_days=30,
                                               notes="3 Odoo-brand CRM seats with priority support")
        QuotationTemplateLine.objects.create(template=tpl, product=crm, variant=odoo, quantity=3)
        QuotationTemplateLine.objects.create(template=tpl, product=support, quantity=1)
        tpl2 = QuotationTemplate.objects.create(name="Enterprise CRM Yearly", plan=plans["crm_y"], validity_days=15)
        QuotationTemplateLine.objects.create(template=tpl2, product=crm, variant=odoo, quantity=25)
        QuotationTemplateLine.objects.create(template=tpl2, product=analytics, quantity=1)
        QuotationTemplateLine.objects.create(template=tpl2, product=storage, quantity=2)
        return {"plans": plans, "crm": crm, "odoo": odoo, "acc": acc, "hr": hr, "storage": storage,
                "support": support, "analytics": analytics}

    def customers(self, n):
        rows = []
        for i in range(n):
            base = COMPANIES[i % len(COMPANIES)]
            name = base if i < len(COMPANIES) else f"{base} {i // len(COMPANIES) + 1}"
            slug = name.lower().replace(" ", "")
            rows.append(Customer(name=name, email=f"accounts@{slug}.example", phone=f"+91 98{self.rng.randint(10000000, 99999999)}",
                                 address=f"{self.rng.randint(1, 400)} MG Road", state=self.rng.choice(STATES),
                                 gstin=f"24AAACB{1000 + i}Z{i % 10}" if i % 3 else ""))
        customers = Customer.objects.bulk_create(rows, batch_size=2000)
        demo = customers[0]
        demo.email, demo.state = "customer@brightloop.test", "Gujarat"
        demo.user = User.objects.get(email="customer@brightloop.test")
        demo.save()
        return customers

    # ------------------------------------------------------------------ subscriptions and history
    def subscriptions(self, cat, customers, n):
        rng, today = self.rng, self.today
        plans = cat["plans"]
        discounts = list(Discount.objects.all())
        scopes = {}
        for d_id, p_id in Discount.products.through.objects.values_list("discount_id", "product_id"):
            scopes.setdefault(d_id, set()).add(p_id)
        company_state = settings.COMPANY["state"]
        plan_weights = [("crm_m", 40), ("crm_y", 15), ("acc_m", 25), ("hr_w", 12), ("sandbox", 3)]
        keys = [k for k, w in plan_weights for _ in range(w)]
        admin = User.objects.get(email="admin@brightloop.test")

        subs, line_specs, sub_meta = [], [], []
        seq = {}

        def number(prefix, year):
            seq[(prefix, year)] = seq.get((prefix, year), 0) + 1
            return f"{prefix}-{year}-{seq[(prefix, year)]:05d}"

        for i in range(n):
            customer = customers[0] if i < 3 else rng.choice(customers)
            plan_key = rng.choice(keys)
            plan = plans[plan_key]
            roll = rng.random()
            if i < 8:  # due today: shows up in the billing run demo
                plan_key, plan = "crm_m", plans["crm_m"]
                start = _months_back(today, rng.randint(1, 6))  # a period starts exactly today
                status = "active"
            elif roll < 0.04:
                status, start = "draft", today + timedelta(days=rng.randint(1, 20))
            elif roll < 0.09:
                status, start = "quotation", today + timedelta(days=rng.randint(1, 20))
            elif roll < 0.12:
                status, start = "confirmed", today + timedelta(days=rng.randint(3, 25))
            elif roll < 0.16:
                status, start = "paused", today - timedelta(days=rng.randint(60, 300))
            elif roll < 0.26:
                status, start = "closed", today - timedelta(days=rng.randint(120, 420))
            else:
                status, start = "active", today - timedelta(days=rng.randint(5, 420))
            if plan_key == "sandbox" and status in ("active", "paused", "closed"):
                start = today - timedelta(days=rng.randint(3, 25))
            expiry = None
            if plan_key == "crm_y":
                expiry = _months_back(start, -24)
            elif plan_key == "hr_w":
                expiry = start + timedelta(weeks=rng.choice([26, 52]))
            elif plan_key == "sandbox":
                expiry = start + timedelta(days=30)
            elif rng.random() < 0.5:
                expiry = _months_back(start, -12)
            # A slice of renewals coming up in the next 90 days.
            if status == "active" and plan_key in ("crm_m", "acc_m") and rng.random() < 0.25:
                expiry = today + timedelta(days=rng.randint(5, 90))
            qty = rng.choice([1, 2, 3, 5, 5, 8, 10]) if plan_key != "crm_y" else rng.choice([5, 10, 25])
            variant = cat["odoo"] if plan.product_id == cat["crm"].id and rng.random() < 0.6 else None
            lines = [(plan.product, variant, qty)]
            if rng.random() < 0.4:
                lines.append((rng.choice([cat["support"], cat["storage"], cat["analytics"]]), None, rng.choice([1, 2])))
            subs.append(Subscription(number=number("SUB", start.year if start <= today else today.year), customer=customer,
                                     plan=plan, status=status, start_date=start, expiry_date=expiry,
                                     payment_term_days=rng.choice([0, 15, 15, 30, 45]), created_by=admin,
                                     quotation_valid_until=today + timedelta(days=30) if status == "quotation" else None))
            line_specs.append(lines)
            sub_meta.append({"due_today": i < 8})

        subs = Subscription.objects.bulk_create(subs, batch_size=2000)
        sub_lines, events = [], []
        for sub, lines in zip(subs, line_specs):
            for product, variant, qty in lines:
                sub_lines.append(SubscriptionLine(subscription=sub, product=product, variant=variant, quantity=qty,
                                                  unit_price=default_unit_price(sub.plan, product, variant),
                                                  tax_group=product.tax_group))
            path = {"draft": ["draft"], "quotation": ["draft", "quotation"],
                    "confirmed": ["draft", "quotation", "confirmed"],
                    "active": ["draft", "quotation", "confirmed", "active"],
                    "paused": ["draft", "quotation", "confirmed", "active", "paused"],
                    "closed": ["draft", "quotation", "confirmed", "active", "closed"]}[sub.status]
            prev = ""
            for st in path:
                events.append(SubscriptionEvent(subscription=sub, from_status=prev, to_status=st, user=admin,
                                                note="Imported from spreadsheet"))
                prev = st
        SubscriptionLine.objects.bulk_create(sub_lines, batch_size=5000)
        SubscriptionEvent.objects.bulk_create(events, batch_size=5000)
        lines_by_sub = {}
        for l in sub_lines:
            lines_by_sub.setdefault(l.subscription_id, []).append(l)

        invoices, inv_lines, pay_plans = [], [], []
        used = {}
        for sub, meta in zip(subs, sub_meta):
            if sub.status in ("draft", "quotation", "confirmed"):
                continue
            period = sub.plan.billing_period
            end_billing = today
            if sub.status == "closed":
                sub.closed_at = min(today - timedelta(days=rng.randint(1, 60)), sub.start_date + timedelta(days=rng.randint(60, 300)))
                end_billing = sub.closed_at
            if sub.status == "paused":
                end_billing = today - timedelta(days=rng.randint(20, 50))
            p = sub.start_date
            while p <= end_billing and (not sub.expiry_date or p < sub.expiry_date):
                if meta["due_today"] and next_period_start(p, period, sub.start_date) > today:
                    break  # leave the current period for the live billing run
                inputs = [LineInput(l.product_id, l.product.name + (f" ({l.variant.label})" if l.variant else ""),
                                    l.quantity, l.unit_price, l.tax_group) for l in lines_by_sub[sub.id]]
                priced = price_lines(inputs, discounts, scopes, p, sub.customer.state, company_state)
                for d in priced.discounts_used:
                    d.used_count += 1
                    used[d.id] = used.get(d.id, 0) + 1
                age = (today - p).days
                due = p + timedelta(days=sub.payment_term_days)
                r = rng.random()
                if age <= 2 and r < 0.4:
                    status = "draft"
                elif age > 45:
                    status = "paid" if r < 0.95 else "confirmed"
                else:
                    status = "paid" if r < 0.55 else "confirmed"
                inv = Invoice(number=number("INV", p.year), subscription=sub, customer=sub.customer,
                              customer_snapshot={"name": sub.customer.name, "email": sub.customer.email,
                                                 "address": sub.customer.address, "state": sub.customer.state,
                                                 "gstin": sub.customer.gstin},
                              period_start=p, period_end=next_period_start(p, period, sub.start_date) - timedelta(days=1),
                              invoice_date=p, due_date=due, status=status, subtotal=priced.subtotal,
                              discount_total=priced.discount_total, tax_total=priced.tax_total, total=priced.total,
                              amount_paid=D(0), applied_discounts=[d.id for d in priced.discounts_used],
                              sent_at=None)
                if status == "paid":
                    inv.amount_paid = priced.total
                    pay_plans.append((len(invoices), [(priced.total, p + timedelta(days=rng.randint(0, max(1, sub.payment_term_days + 5))))]))
                elif status == "confirmed" and rng.random() < 0.25:
                    part = q(priced.total * D("0.4"))
                    inv.amount_paid = part
                    pay_plans.append((len(invoices), [(part, p + timedelta(days=rng.randint(1, 20)))]))
                invoices.append(inv)
                inv_lines.append(priced.lines)
                p = next_period_start(p, period, sub.start_date)
            sub.next_invoice_date = p if sub.status in ("active", "paused") else None
        Subscription.objects.bulk_update(subs, ["next_invoice_date", "closed_at"], batch_size=2000)

        invoices = Invoice.objects.bulk_create(invoices, batch_size=2000)
        rows = []
        for inv, priced_lines in zip(invoices, inv_lines):
            for pl in priced_lines:
                rows.append(InvoiceLine(invoice=inv, product_id=pl.product_id, description=pl.description,
                                        quantity=pl.quantity, unit_price=pl.unit_price, subtotal=pl.subtotal,
                                        discount=pl.discount, discount_name=pl.discount_name,
                                        discount_amount=pl.discount_amount, taxes=pl.taxes, tax_amount=pl.tax_amount,
                                        total=pl.total))
        InvoiceLine.objects.bulk_create(rows, batch_size=5000)
        methods = [m for m, _ in Payment.Method.choices]
        payments = []
        for idx, plan in pay_plans:
            for amount, when in plan:
                payments.append(Payment(invoice=invoices[idx], method=rng.choice(methods), amount=amount,
                                        date=min(when, today), note="Bank statement import", created_by=admin))
        Payment.objects.bulk_create(payments, batch_size=5000)
        for d_id, count in used.items():
            Discount.objects.filter(pk=d_id).update(used_count=count)
        Sequence.objects.bulk_create([Sequence(key=f"{prefix}-{year}", value=v) for (prefix, year), v in seq.items()])
        self.stdout.write(f"Created {len(subs)} subscriptions, {len(invoices)} invoices, {len(payments)} payments.")


def _months_back(day: date, months: int) -> date:
    from core.money import add_months
    return add_months(day, -months)
