"""Server-side invoice PDF: content matches the invoice, access follows invoice visibility, emails attach it."""
from datetime import date
from io import BytesIO

from pypdf import PdfReader

from accounts.models import User
from core import services
from core.models import Customer, Invoice
from core.pdf import inr

from .conftest import client_for, make_user


def pdf_text(data: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)


def issued_invoice(golden) -> Invoice:
    services.run_billing(date(2026, 1, 15))
    return services.confirm_invoice(Invoice.objects.get())


def test_indian_number_format():
    assert inr("1234567.5") == "12,34,567.50"
    assert inr("999") == "999.00"
    assert inr("100000") == "1,00,000.00"
    assert inr("-1500") == "-1,500.00"
    assert inr(None) == "0.00"


def test_pdf_matches_the_invoice(staff_user, golden):
    inv = issued_invoice(golden)
    r = client_for(staff_user).get(f"/api/invoices/{inv.pk}/pdf")
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert r["Content-Disposition"] == f'attachment; filename="{inv.number}.pdf"'
    assert r.content.startswith(b"%PDF")
    text = pdf_text(r.content)
    for expected in (inv.number, "TAX INVOICE", "Acme Traders", "9,935.60", "9,300.00", "-880.00",
                     "CGST 9%", "SGST 9%", "Volume 10%", "intra-state"):
        assert expected in text, expected

    inline = client_for(staff_user).get(f"/api/invoices/{inv.pk}/pdf?inline=1")
    assert inline["Content-Disposition"].startswith("inline;")


def test_pdf_uses_the_issued_snapshot(staff_user, golden):
    inv = issued_invoice(golden)
    Customer.objects.filter(pk=golden["customer"].pk).update(name="Renamed Later Ltd", state="Maharashtra")
    text = pdf_text(client_for(staff_user).get(f"/api/invoices/{inv.pk}/pdf").content)
    assert "Acme Traders" in text and "Renamed Later" not in text and "CGST 9%" in text


def test_paid_invoice_shows_payments_and_zero_balance(staff_user, golden):
    inv = issued_invoice(golden)
    services.record_payment(inv, "upi", inv.total, date(2026, 1, 20), "", None)
    text = pdf_text(client_for(staff_user).get(f"/api/invoices/{inv.pk}/pdf").content)
    assert "Paid" in text and "PAYMENTS RECEIVED" in text
    assert "Balance due (INR)" in text and text.split("Balance due (INR)")[1].split()[0] == "0.00"


def test_customers_download_only_their_own_issued_invoices(golden):
    owner = make_user("acme@example.com", User.Role.CUSTOMER)
    golden["customer"].user = owner
    golden["customer"].save()
    other = make_user("other@example.com", User.Role.CUSTOMER)
    Customer.objects.create(name="Other", email="other@example.com", user=other)

    services.run_billing(date(2026, 1, 15))
    draft = Invoice.objects.get()
    assert client_for(owner).get(f"/api/invoices/{draft.pk}/pdf").status_code == 404  # drafts are not issued yet

    services.confirm_invoice(draft)
    assert client_for(owner).get(f"/api/invoices/{draft.pk}/pdf").status_code == 200
    denied = client_for(other).get(f"/api/invoices/{draft.pk}/pdf")
    assert denied.status_code == 404 and denied.json()["detail"]  # errors stay readable JSON


def test_staff_can_preview_a_draft(staff_user, golden):
    services.run_billing(date(2026, 1, 15))
    draft = Invoice.objects.get()
    text = pdf_text(client_for(staff_user).get(f"/api/invoices/{draft.pk}/pdf").content)
    assert "DRAFT" in text


def test_sent_invoice_email_has_the_pdf_attached(staff_user, golden, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    from django.core import mail

    inv = issued_invoice(golden)
    assert client_for(staff_user).post(f"/api/invoices/{inv.pk}/send").status_code == 200
    (message,) = mail.outbox
    (name, content, mimetype) = message.attachments[0]
    assert name == f"{inv.number}.pdf" and mimetype == "application/pdf" and content.startswith(b"%PDF")
    assert inv.number in pdf_text(content) and "attached as a PDF" in message.body
