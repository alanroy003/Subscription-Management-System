"""Free trials, built on the normal subscription engine.

A trial is a subscription on a plan marked `is_trial` (priced 0, auto-closing): it bills a 0-rupee invoice that is
settled at once, closes itself after `trial_days`, and can be converted into a paid subscription that starts when
the trial ends. One trial per customer, enforced in `services.validate_for_confirmation`.
"""
from datetime import date, timedelta

from django.db import transaction

from . import audit
from .models import Customer, Plan, Subscription, SubscriptionEvent, SubscriptionLine
from .pricing import default_unit_price
from .services import (
    DomainError,
    _activate,
    bill_subscription,
    customer_had_trial,
    next_number,
    validate_for_confirmation,
)

S = Subscription.Status


def trial_plan(today: date | None = None) -> Plan | None:
    """The free trial currently on offer (the first available trial plan)."""
    today = today or date.today()
    for plan in Plan.objects.filter(is_trial=True).select_related("product").order_by("id"):
        if plan.is_available_on(today) and plan.product_id:
            return plan
    return None


def paid_plans(today: date | None = None) -> list[Plan]:
    today = today or date.today()
    return [p for p in Plan.objects.filter(is_trial=False).order_by("name") if p.is_available_on(today)]


def _event(sub: Subscription, old: str, user, note: str) -> None:
    SubscriptionEvent.objects.create(subscription=sub, from_status=old, to_status=sub.status, user=user, note=note)


def start_trial(customer: Customer, user=None) -> Subscription:
    """Start the customer's free trial today. Bills its 0-rupee first invoice straight away."""
    today = date.today()
    plan = trial_plan(today)
    if plan is None:
        raise DomainError("No free trial is offered right now.")
    with transaction.atomic():
        Customer.objects.select_for_update().get(pk=customer.pk)  # two clicks cannot start two trials
        if customer_had_trial(customer.pk):
            raise DomainError("This customer has already had a free trial.")
        sub = Subscription.objects.create(
            number=next_number("SUB"), customer=customer, plan=plan, status=S.DRAFT, start_date=today,
            expiry_date=today + timedelta(days=plan.trial_days), payment_term_days=0, created_by=user,
            notes=f"Free trial ({plan.trial_days} days)",
        )
        SubscriptionLine.objects.create(
            subscription=sub, product=plan.product, quantity=max(1, plan.min_quantity),
            unit_price=default_unit_price(plan, plan.product), tax_group=plan.product.tax_group,
        )
        validate_for_confirmation(sub)
        _activate(sub)
        sub.save()
        _event(sub, S.DRAFT, user, f"Free trial started, ends {sub.expiry_date:%d %b %Y}")
        audit.record("subscription.trial_started", sub, actor=user,
                     changes={"plan": plan.name, "days": plan.trial_days, "expiry_date": sub.expiry_date})
        bill_subscription(sub.pk, today, locked=sub)  # the 0-rupee invoice, settled automatically
    return sub


def convert_trial(trial: Subscription, plan_id: int, user=None) -> Subscription:
    """Create the paid subscription that follows a trial: same products, the chosen plan's prices, starting when the
    trial ends (or today if it already ended)."""
    today = date.today()
    with transaction.atomic():
        trial = Subscription.objects.select_for_update().select_related("plan", "customer").get(pk=trial.pk)
        if not trial.plan.is_trial:
            raise DomainError("Only a free trial can be converted.")
        if trial.converted_to_id:
            raise DomainError(f"This trial was already converted to {trial.converted_to.number}.")
        if trial.status not in (S.ACTIVE, S.PAUSED, S.CLOSED):
            raise DomainError("The trial has not started yet.")
        target = Plan.objects.select_related("product").filter(pk=plan_id, is_trial=False).first()
        if target is None or not target.is_available_on(today):
            raise DomainError("Choose a paid plan that is available today.")

        start = max(today, trial.expiry_date or today)
        paid = Subscription.objects.create(
            number=next_number("SUB"), customer=trial.customer, plan=target, status=S.DRAFT, start_date=start,
            payment_term_days=15, created_by=user, notes=f"Converted from free trial {trial.number}",
        )
        lines = list(trial.lines.select_related("product", "variant"))
        for line in lines:
            quantity = line.quantity
            if line.product_id == target.product_id:
                quantity = max(quantity, target.min_quantity)
            SubscriptionLine.objects.create(
                subscription=paid, product=line.product, variant=line.variant, quantity=quantity,
                unit_price=default_unit_price(target, line.product, line.variant), tax_group=line.product.tax_group,
            )
        if target.product_id and not any(line.product_id == target.product_id for line in lines):
            SubscriptionLine.objects.create(
                subscription=paid, product=target.product, quantity=max(1, target.min_quantity),
                unit_price=default_unit_price(target, target.product), tax_group=target.product.tax_group,
            )
        validate_for_confirmation(paid)
        paid.status = S.CONFIRMED
        if start <= today:
            _activate(paid)
        paid.save()
        _event(paid, S.DRAFT, user, f"Created from free trial {trial.number}")
        trial.converted_to = paid
        trial.save(update_fields=["converted_to"])
        _event(
            trial,
            trial.status,
            user,
            f"Converted to paid plan {target.name} ({paid.number}), starting {start:%d %b %Y}",
        )
        audit.record("subscription.trial_converted", trial, actor=user,
                     changes={"paid_subscription": paid.number, "plan": target.name, "starts": start})
        if paid.status == S.ACTIVE:
            bill_subscription(paid.pk, today, locked=paid)
    return paid


def trial_info(customer: Customer | None) -> dict:
    """What the portal (or a staff screen) needs to offer, show or convert a trial."""
    today = date.today()
    plan = trial_plan(today)
    current = None
    if customer is not None:
        current = (Subscription.objects.filter(customer=customer, plan__is_trial=True).exclude(status=S.DRAFT)
                   .select_related("converted_to").order_by("-id").first())
    return {
        "offered": plan is not None,
        "plan": {"id": plan.pk, "name": plan.name, "days": plan.trial_days} if plan else None,
        "eligible": plan is not None and customer is not None and current is None,
        "current": None if current is None else {
            "id": current.pk, "number": current.number, "status": current.status,
            "expiry_date": current.expiry_date,
            "days_left": max(0, (current.expiry_date - today).days) if current.expiry_date else None,
            "converted_to": current.converted_to.number if current.converted_to_id else None,
            "converted_to_id": current.converted_to_id,
        },
        "paid_plans": [{"id": p.pk, "name": p.name, "price": str(p.price), "billing_period": p.billing_period}
                       for p in paid_plans(today)],
    }
