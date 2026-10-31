"""Pure pricing rules: unit prices, discount eligibility and tax. No database writes."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .money import ZERO, q


def default_unit_price(plan, product, variant=None) -> Decimal:
    """The plan price is the per-period price of its base product; other lines use the variant price."""
    extra = variant.price_extra if variant else ZERO
    if plan is not None and plan.product_id and product.id == plan.product_id:
        return plan.price + extra
    return product.sales_price + extra


def tax_components(base: Decimal, tax_group, customer_state: str, company_state: str) -> list[dict]:
    """GST: CGST+SGST when the customer is in the company's state (or unknown), IGST otherwise."""
    if tax_group is None or not tax_group.is_active or tax_group.rate == 0:
        return []
    rate = Decimal(tax_group.rate)
    if tax_group.mode == "gst":
        same_state = not customer_state or customer_state.strip().lower() == company_state.strip().lower()
        if same_state:
            half = rate / 2
            return [
                {"name": "CGST", "rate": str(half), "amount": str(q(base * half / 100))},
                {"name": "SGST", "rate": str(half), "amount": str(q(base * half / 100))},
            ]
        return [{"name": "IGST", "rate": str(rate), "amount": str(q(base * rate / 100))}]
    return [{"name": tax_group.name, "rate": str(rate), "amount": str(q(base * rate / 100))}]


def discount_is_open(discount, on_date: date) -> bool:
    if not discount.is_active:
        return False
    if discount.start_date and on_date < discount.start_date:
        return False
    if discount.end_date and on_date > discount.end_date:
        return False
    if discount.usage_limit is not None and discount.used_count >= discount.usage_limit:
        return False
    return True


def discount_value(discount, base: Decimal) -> Decimal:
    if base <= 0:
        return ZERO
    if discount.kind == "percent":
        return min(q(base * discount.value / 100), base)
    return min(q(discount.value), base)


@dataclass
class LineInput:
    product_id: int | None
    description: str
    quantity: int
    unit_price: Decimal
    tax_group: object = None


@dataclass
class PricedLine:
    product_id: int | None
    description: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    discount: object = None
    discount_name: str = ""
    discount_amount: Decimal = ZERO
    taxes: list = field(default_factory=list)
    tax_amount: Decimal = ZERO
    total: Decimal = ZERO


@dataclass
class PricedInvoice:
    lines: list
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    discounts_used: list


def price_lines(lines: list[LineInput], discounts: list, product_scopes: dict, on_date: date,
                customer_state: str, company_state: str) -> PricedInvoice:
    """Price an invoice.

    Discounts are applied before tax: the single best product-scoped discount per line, then at most one
    subscription-level discount on what remains, allocated to lines in proportion (remainder on the last line).
    `product_scopes` maps discount id -> set of product ids for product-scoped discounts.
    """
    open_discounts = [d for d in discounts if discount_is_open(d, on_date)]
    priced = [
        PricedLine(l.product_id, l.description, l.quantity, q(l.unit_price), q(l.unit_price * l.quantity))
        for l in lines
    ]
    invoice_subtotal = sum((p.subtotal for p in priced), ZERO)
    used = []

    for p in priced:
        best, best_amount = None, ZERO
        for d in open_discounts:
            if d.scope != "products" or p.product_id not in product_scopes.get(d.id, set()):
                continue
            if invoice_subtotal < d.min_amount or p.quantity < d.min_quantity:
                continue
            amount = discount_value(d, p.subtotal)
            if amount > best_amount:
                best, best_amount = d, amount
        if best:
            p.discount, p.discount_name, p.discount_amount = best, best.name, best_amount
            if best not in used:
                used.append(best)

    remaining = sum((p.subtotal - p.discount_amount for p in priced), ZERO)
    total_qty = sum(p.quantity for p in priced)
    best, best_amount = None, ZERO
    for d in open_discounts:
        if d.scope != "all" or invoice_subtotal < d.min_amount or total_qty < d.min_quantity:
            continue
        amount = discount_value(d, remaining)
        if amount > best_amount:
            best, best_amount = d, amount
    if best and remaining > 0:
        allocated = ZERO
        bases = [p.subtotal - p.discount_amount for p in priced]
        for i, p in enumerate(priced):
            share = best_amount - allocated if i == len(priced) - 1 else q(best_amount * bases[i] / remaining)
            allocated += share
            if share:
                p.discount_amount += share
                p.discount_name = f"{p.discount_name} + {best.name}" if p.discount_name else best.name
                p.discount = p.discount or best
        used.append(best)

    for p, src in zip(priced, lines):
        base = p.subtotal - p.discount_amount
        p.taxes = tax_components(base, src.tax_group, customer_state, company_state)
        p.tax_amount = sum((Decimal(t["amount"]) for t in p.taxes), ZERO)
        p.total = base + p.tax_amount

    return PricedInvoice(
        lines=priced,
        subtotal=invoice_subtotal,
        discount_total=sum((p.discount_amount for p in priced), ZERO),
        tax_total=sum((p.tax_amount for p in priced), ZERO),
        total=sum((p.total for p in priced), ZERO),
        discounts_used=used,
    )
