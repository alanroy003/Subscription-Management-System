"""Server-side invoice PDF.

Rendered from an HTML template with xhtml2pdf (pure Python, so it works the same natively on Windows and in Docker).
The PDF is built only from what the invoice stored when it was issued (line, tax and customer snapshots), so a PDF
printed today matches the one emailed on the day of issue, whatever changed in the catalog since.
"""
from collections import OrderedDict
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from .models import Invoice
from .money import ZERO, q


class PdfError(Exception):
    pass


def inr(value) -> str:
    """Indian digit grouping: 1234567.5 -> '12,34,567.50'."""
    amount = q(Decimal(value or 0))
    sign = "-" if amount < 0 else ""
    whole, fraction = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{whole}.{fraction}"


def _tax_summary(lines) -> list[dict]:
    """Totals per tax component (e.g. CGST 9%, SGST 9%) across all lines, in first-seen order."""
    summary: OrderedDict = OrderedDict()
    for line in lines:
        for tax in line.taxes or []:
            key = (tax["name"], str(Decimal(tax["rate"]).normalize()))
            summary[key] = summary.get(key, ZERO) + Decimal(tax["amount"])
    return [{"label": f"{name} {rate}%", "amount": inr(amount)} for (name, rate), amount in summary.items()]


def invoice_filename(invoice: Invoice) -> str:
    return f"{invoice.number}.pdf"


def render_invoice_pdf(invoice: Invoice) -> bytes:
    lines = list(invoice.lines.order_by("id"))
    payments = list(invoice.payments.order_by("date", "id"))
    customer = invoice.customer_snapshot or {}
    context = {
        "invoice": invoice,
        "company": settings.COMPANY,
        "customer": customer,
        "status": "Draft" if invoice.status == Invoice.Status.DRAFT else invoice.get_status_display(),
        "lines": [
            {
                "description": line.description,
                "quantity": line.quantity,
                "unit_price": inr(line.unit_price),
                "subtotal": inr(line.subtotal),
                "discount_name": line.discount_name,
                "discount_amount": inr(line.discount_amount) if line.discount_amount else "",
                "taxes": ", ".join(f"{t['name']} {inr(t['amount'])}" for t in line.taxes or []),
                "total": inr(line.total),
            }
            for line in lines
        ],
        "tax_summary": _tax_summary(lines),
        "subtotal": inr(invoice.subtotal),
        "discount_total": inr(invoice.discount_total) if invoice.discount_total else "",
        "total": inr(invoice.total),
        "amount_paid": inr(invoice.amount_paid) if invoice.amount_paid else "",
        "balance": inr(invoice.balance),
        "payments": [{"date": p.date, "method": p.get_method_display(), "amount": inr(p.amount)} for p in payments],
        "same_state": (not customer.get("state")
                       or customer.get("state", "").lower() == settings.COMPANY["state"].lower()),
    }
    html = render_to_string("core/invoice_pdf.html", context)
    out = BytesIO()
    result = pisa.CreatePDF(html, dest=out, encoding="utf-8")
    if result.err:
        raise PdfError(f"Could not render the PDF for invoice {invoice.number}.")
    return out.getvalue()
