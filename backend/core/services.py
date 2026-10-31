"""Domain services: numbering, subscription lifecycle, billing engine, invoices and payments.

Every state change happens inside a transaction and leaves a SubscriptionEvent where relevant.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import (
    BillingRun,
    Customer,
    Discount,
    Invoice,
    InvoiceLine,
    Payment,
    Sequence,
    Subscription,
    SubscriptionEvent,
)
from .money import ZERO, next_period_start, q
from .parallel import map_parallel
from .pricing import LineInput, price_lines

S = Subscription.Status


class DomainError(Exception):
    """A business rule was violated; shown to the user as a 400."""


def next_number(prefix: str, on: date | None = None) -> str:
    """Gap-free per prefix and year: one atomic upsert, the row stays locked until the caller commits."""
    from django.db import connection
    year = (on or date.today()).year
    key = f"{prefix}-{year}"
    table = Sequence._meta.db_table
    with connection.cursor() as cur:
        cur.execute(f"INSERT INTO {table} (key, value) VALUES (%s, 1) "
                    f"ON CONFLICT (key) DO UPDATE SET value = {table}.value + 1 RETURNING value", [key])
        value = cur.fetchone()[0]
    return f"{key}-{value:05d}"


# ---------------------------------------------------------------- subscription lifecycle

def _log(sub: Subscription, old: str, user, note: str = "") -> None:
    SubscriptionEvent.objects.create(subscription=sub, from_status=old, to_status=sub.status, user=user, note=note)


def validate_for_confirmation(sub: Subscription) -> None:
    lines = list(sub.lines.all())
    if not lines:
        raise DomainError("Add at least one product line before confirming.")
    plan = sub.plan
    if not plan.is_available_on(sub.start_date):
        raise DomainError(f"Plan '{plan.name}' is not available on {sub.start_date}.")
    base_qty = sum(l.quantity for l in lines if plan.product_id is None or l.product_id == plan.product_id)
    if plan.product_id and base_qty == 0:
        base_qty = sum(l.quantity for l in lines)
    if base_qty < plan.min_quantity:
        raise DomainError(f"Plan '{plan.name}' requires a minimum quantity of {plan.min_quantity}.")
    if sub.expiry_date and sub.expiry_date <= sub.start_date:
        raise DomainError("Expiry date must be after the start date.")


def available_actions(sub: Subscription, user) -> list[str]:
    team = user.is_team
    plan = sub.plan
    today = date.today()
    actions = []
    if sub.status == S.DRAFT and team:
        actions += ["send_quotation", "confirm"]
    if sub.status == S.QUOTATION:
        if team or (sub.quotation_valid_until is None or sub.quotation_valid_until >= today):
            actions.append("confirm")
    if sub.status == S.CONFIRMED and team and sub.start_date <= today:
        actions.append("activate")
    if sub.status == S.ACTIVE and plan.pausable:
        actions.append("pause")
    if sub.status == S.PAUSED:
        actions.append("resume")
    if sub.status in (S.ACTIVE, S.PAUSED) and plan.renewable and sub.expiry_date:
        actions.append("renew")
    if (
        sub.status == S.CLOSED
        and plan.renewable
        and sub.expiry_date
        and sub.closed_at
        and sub.closed_at >= sub.expiry_date
    ):
        actions.append("renew")
    if sub.status in (S.ACTIVE, S.PAUSED) and (plan.closable or user.is_admin):
        actions.append("close")
    if sub.status in (S.DRAFT, S.QUOTATION, S.CONFIRMED) and team:
        actions.append("close")
    return actions


def transition(sub: Subscription, action: str, user, note: str = "") -> Subscription:
    with transaction.atomic():
        sub = Subscription.objects.select_for_update().select_related("plan", "customer").get(pk=sub.pk)
        if action not in available_actions(sub, user):
            raise DomainError(f"Action '{action}' is not allowed while the subscription is {sub.status}.")
        old = sub.status
        today = date.today()
        if action == "send_quotation":
            validate_for_confirmation(sub)
            sub.status = S.QUOTATION
            if not sub.quotation_valid_until:
                days = sub.template.validity_days if sub.template else 30
                sub.quotation_valid_until = today + timedelta(days=days)
        elif action == "confirm":
            validate_for_confirmation(sub)
            sub.status = S.CONFIRMED
        elif action == "activate":
            _activate(sub)
        elif action == "pause":
            sub.status = S.PAUSED
        elif action == "resume":
            sub.status = S.ACTIVE
            # Periods that started while paused are not billed: move to the first period start >= today.
            while sub.next_invoice_date and sub.next_invoice_date < today:
                sub.next_invoice_date = next_period_start(
                    sub.next_invoice_date, sub.plan.billing_period, sub.start_date
                )
        elif action == "renew":
            term = sub.expiry_date - sub.start_date
            sub.expiry_date = sub.expiry_date + term
            if sub.status == S.CLOSED:
                sub.status = S.ACTIVE
                sub.closed_at = None
            note = note or f"Renewed until {sub.expiry_date}"
        elif action == "close":
            sub.status = S.CLOSED
            sub.closed_at = today
        events = [SubscriptionEvent(subscription=sub, from_status=old, to_status=sub.status, user=user, note=note)]
        if action == "confirm" and sub.start_date <= today:
            _activate(sub)
            events.append(SubscriptionEvent(subscription=sub, from_status=S.CONFIRMED, to_status=S.ACTIVE, user=user,
                                            note="Started automatically"))
        sub.save()
        SubscriptionEvent.objects.bulk_create(events)
        if sub.status == S.ACTIVE and action in ("confirm", "activate", "renew"):
            bill_subscription(sub.pk, today, locked=sub)  # first invoice is billed in advance on activation
    return sub


def _activate(sub: Subscription) -> None:
    sub.status = S.ACTIVE
    if sub.next_invoice_date is None:
        sub.next_invoice_date = sub.start_date


# ---------------------------------------------------------------- billing engine

@dataclass
class BillItem:
    subscription_number: str
    period_start: date
    total: Decimal
    status: str  # created | skipped | failed | closed | activated
    error: str = ""
    invoice_number: str = ""

    def as_dict(self):
        return {"subscription_number": self.subscription_number, "period_start": str(self.period_start),
                "total": str(self.total), "status": self.status, "error": self.error,
                "invoice_number": self.invoice_number}


def _period_end(sub: Subscription, period_start: date) -> date:
    return next_period_start(period_start, sub.plan.billing_period, sub.start_date) - timedelta(days=1)


def load_discounts() -> tuple[list, dict]:
    discounts = list(Discount.objects.filter(is_active=True))
    scopes: dict[int, set] = {}
    for d_id, p_id in Discount.products.through.objects.filter(discount__in=discounts).values_list(
        "discount_id", "product_id"
    ):
        scopes.setdefault(d_id, set()).add(p_id)
    return discounts, scopes


def create_invoice(sub: Subscription, period_start: date, catalog: tuple | None = None, claim: bool = True) -> Invoice:
    """Create the invoice for one period. Caller holds the subscription lock.

    The unique (subscription, period_start) constraint makes a second invoice for the same period impossible.
    `catalog` is the (discounts, scopes) pair, loaded once per billing run; usage limits are enforced atomically
    when claimed, so a stale cached count can never over-apply a discount.
    """
    customer: Customer = sub.customer
    lines = list(sub.lines.select_related("product", "variant", "tax_group", "product__tax_group"))
    if not lines:
        raise DomainError("Subscription has no lines.")
    inputs = [
        LineInput(
            product_id=l.product_id,
            description=l.description or (f"{l.product.name} ({l.variant.label})" if l.variant else l.product.name),
            quantity=l.quantity,
            unit_price=l.unit_price,
            tax_group=l.tax_group or l.product.tax_group,
        )
        for l in lines
    ]
    discounts, scopes = catalog or load_discounts()
    while True:
        priced = price_lines(inputs, discounts, scopes, period_start, customer.state, settings.COMPANY["state"])
        # A dry run never writes usage counts (it is rolled back anyway); it prices against the cached counts.
        exhausted = _claim_discounts(priced.discounts_used) if claim else None
        if exhausted is None:
            break
        discounts = [d for d in discounts if d.pk != exhausted]  # lost a race for the last use: price without it

    invoice_date = max(period_start, sub.start_date)
    invoice = Invoice.objects.create(
        number=f"DRAFT-{sub.pk}-{period_start:%Y%m%d}",  # final number assigned just before commit
        subscription=sub,
        customer=customer,
        customer_snapshot={"name": customer.name, "email": customer.email, "address": customer.address,
                           "state": customer.state, "gstin": customer.gstin},
        period_start=period_start,
        period_end=_period_end(sub, period_start),
        invoice_date=invoice_date,
        due_date=invoice_date + timedelta(days=sub.payment_term_days),
        subtotal=priced.subtotal,
        discount_total=priced.discount_total,
        tax_total=priced.tax_total,
        total=priced.total,
        applied_discounts=[d.id for d in priced.discounts_used],
    )
    InvoiceLine.objects.bulk_create([
        InvoiceLine(invoice=invoice, product_id=p.product_id, description=p.description, quantity=p.quantity,
                    unit_price=p.unit_price, subtotal=p.subtotal, discount=p.discount, discount_name=p.discount_name,
                    discount_amount=p.discount_amount, taxes=p.taxes, tax_amount=p.tax_amount, total=p.total)
        for p in priced.lines
    ])
    return invoice


def _claim_discounts(used: list) -> int | None:
    """Count one use of each discount atomically. Returns the id of a discount that ran out, if any."""
    from django.db.models import Q

    class _Exhausted(Exception):
        pass

    if not used:
        return None
    if len(used) == 1:  # a single conditional UPDATE is already atomic; no savepoint round trips needed
        d = used[0]
        claimed = Discount.objects.filter(Q(usage_limit__isnull=True) | Q(used_count__lt=F("usage_limit")),
                                          pk=d.pk).update(used_count=F("used_count") + 1)
        return None if claimed else d.pk
    try:
        with transaction.atomic():  # savepoint: all claims or none
            for d in used:
                claimed = Discount.objects.filter(Q(usage_limit__isnull=True) | Q(used_count__lt=F("usage_limit")),
                                                  pk=d.pk).update(used_count=F("used_count") + 1)
                if not claimed:
                    raise _Exhausted(d.pk)
    except _Exhausted as exc:
        return exc.args[0]
    return None


def bill_subscription(sub_id: int, as_of: date, catalog: tuple | None = None, assign_numbers: bool = True,
                      locked: Subscription | None = None) -> list[BillItem]:
    """Bill every due period up to `as_of` (catch-up). Runs in its own transaction (no savepoint when nested).

    `locked` is a subscription the caller already holds with select_for_update in the current transaction.
    """
    items = []
    with transaction.atomic(savepoint=False):
        sub = locked or Subscription.objects.select_for_update().select_related("plan", "customer").get(pk=sub_id)
        if sub.status == S.CONFIRMED and sub.start_date <= as_of:
            old = sub.status
            _activate(sub)
            sub.save()
            _log(sub, old, None, "Started by billing run")
            items.append(BillItem(sub.number, sub.start_date, ZERO, "activated"))
        if sub.status == S.ACTIVE:
            billed_from = sub.next_invoice_date
            created = []
            while sub.next_invoice_date and sub.next_invoice_date <= as_of:
                if sub.expiry_date and sub.next_invoice_date >= sub.expiry_date:
                    break
                created.append(create_invoice(sub, sub.next_invoice_date, catalog, claim=assign_numbers))
                sub.next_invoice_date = next_period_start(
                    sub.next_invoice_date, sub.plan.billing_period, sub.start_date
                )
            if sub.next_invoice_date != billed_from:
                sub.save(update_fields=["next_invoice_date"])
            # Gap-free numbers last, so the sequence row lock is held for the fewest round trips.
            for inv in created:
                if assign_numbers:
                    inv.number = next_number("INV", inv.invoice_date)
                    Invoice.objects.filter(pk=inv.pk).update(number=inv.number)
                else:
                    inv.number = "(preview)"
                items.append(BillItem(sub.number, inv.period_start, inv.total, "created", invoice_number=inv.number))
        if sub.status in (S.ACTIVE, S.PAUSED) and sub.plan.auto_close and sub.expiry_date and sub.expiry_date <= as_of:
            old = sub.status
            sub.status, sub.closed_at = S.CLOSED, sub.expiry_date
            sub.save()
            _log(sub, old, None, "Closed automatically at expiry")
            items.append(BillItem(sub.number, sub.expiry_date, ZERO, "closed"))
    return items


def run_billing(as_of: date | None = None, dry_run: bool = False, user=None) -> BillingRun:
    """Billing day. Each subscription is isolated: one failure never blocks the others.

    A dry run executes the same code and rolls everything back, so the preview is exact.
    """
    as_of = as_of or date.today()
    due = (
        Subscription.objects.filter(status__in=[S.ACTIVE, S.CONFIRMED, S.PAUSED])
        .filter(
            # active and due, confirmed and started, or due for auto-close
            models_q_due(as_of)
        )
        .values_list("id", flat=True)
        .order_by("id")
    )

    def one(sub_id: int) -> list[BillItem]:
        # Each subscription commits on its own (failure isolation); a dry run rolls its own transaction back.
        try:
            with transaction.atomic():
                result = bill_subscription(sub_id, as_of, catalog, assign_numbers=not dry_run)
                if dry_run:
                    transaction.set_rollback(True)
                return result
        except Exception as exc:
            number = Subscription.objects.filter(pk=sub_id).values_list("number", flat=True).first() or str(sub_id)
            return [BillItem(number, as_of, ZERO, "failed", error=str(exc)[:300])]

    catalog = load_discounts()
    items: list[BillItem] = [i for batch in map_parallel(one, list(due)) for i in batch]

    run = BillingRun.objects.create(
        run_date=as_of, dry_run=dry_run, triggered_by=user if user and user.is_authenticated else None,
        created=sum(1 for i in items if i.status == "created"),
        skipped=0, failed=sum(1 for i in items if i.status == "failed"),
        items=[i.as_dict() for i in items], finished_at=timezone.now(),
    )
    return run


def models_q_due(as_of: date):
    from django.db.models import Q
    # An expired subscription (next period at or past expiry) has nothing left to bill until it is renewed.
    not_expired = Q(expiry_date__isnull=True) | Q(expiry_date__gt=F("next_invoice_date"))
    return (
        (Q(status=S.ACTIVE, next_invoice_date__lte=as_of) & not_expired)
        | Q(status=S.CONFIRMED, start_date__lte=as_of)
        | Q(plan__auto_close=True, expiry_date__lte=as_of)
    )


# ---------------------------------------------------------------- invoices and payments

def confirm_invoice(invoice: Invoice) -> Invoice:
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.status != Invoice.Status.DRAFT:
            raise DomainError("Only draft invoices can be confirmed.")
        invoice.status = Invoice.Status.CONFIRMED
        invoice.save(update_fields=["status"])
    return invoice


def cancel_invoice(invoice: Invoice) -> Invoice:
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.status not in (Invoice.Status.DRAFT, Invoice.Status.CONFIRMED):
            raise DomainError("Only draft or confirmed invoices can be cancelled.")
        if invoice.amount_paid > 0:
            raise DomainError("An invoice with payments cannot be cancelled.")
        invoice.status = Invoice.Status.CANCELLED
        invoice.save(update_fields=["status"])
        # Release discount usage so a cancelled invoice does not consume the limit.
        Discount.objects.filter(pk__in=invoice.applied_discounts, used_count__gt=0).update(
            used_count=F("used_count") - 1
        )
    return invoice


def send_invoice(invoice: Invoice) -> Invoice:
    if invoice.status == Invoice.Status.DRAFT:
        invoice = confirm_invoice(invoice)
    if invoice.status == Invoice.Status.CANCELLED:
        raise DomainError("A cancelled invoice cannot be sent.")
    email = invoice.customer_snapshot.get("email") or invoice.customer.email
    link = f"{settings.FRONTEND_URL}/invoices/{invoice.pk}"
    body = (
        f"Dear {invoice.customer_snapshot.get('name')},\n\n"
        f"Invoice {invoice.number} for {invoice.currency} {invoice.total} is due on {invoice.due_date}.\n"
        f"Period: {invoice.period_start} to {invoice.period_end}.\nView and print: {link}\n\n"
        f"{settings.COMPANY['name']}"
    )
    msg = EmailMultiAlternatives(f"Invoice {invoice.number} from {settings.COMPANY['name']}", body,
                                 settings.DEFAULT_FROM_EMAIL, [email])
    msg.send(fail_silently=False)
    invoice.sent_at = timezone.now()
    invoice.save(update_fields=["sent_at"])
    return invoice


def record_payment(invoice: Invoice, method: str, amount: Decimal, on: date, note: str, user) -> Payment:
    amount = q(amount)
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.status != Invoice.Status.CONFIRMED:
            raise DomainError("Payments can only be recorded against confirmed invoices.")
        if amount <= 0:
            raise DomainError("Amount must be positive.")
        if amount > invoice.balance:
            raise DomainError(f"Amount exceeds the outstanding balance of {invoice.balance}.")
        payment = Payment.objects.create(
            invoice=invoice, method=method, amount=amount, date=on, note=note, created_by=user
        )
        invoice.amount_paid += amount
        if invoice.balance == 0:
            invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=["amount_paid", "status"])
    return payment
