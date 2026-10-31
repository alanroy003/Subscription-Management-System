"""Make issued money records tamper-proof in the database itself (Postgres only).

- A confirmed or paid invoice keeps its amounts, parties, period and dates. Only status, amount_paid and sent_at may
  change, and only forward: confirmed -> paid / cancelled. A cancelled invoice never changes again.
- Invoice lines are frozen once their invoice leaves draft.
- Issued invoices cannot be deleted.
- Payments are an append-only ledger: no updates, no deletes (refunds will be separate records).
- Allowed exceptions: ON DELETE SET NULL detaching a deleted product, discount or user; snapshots keep the names.

TRUNCATE (used by `seed --reset` and test teardown) does not fire row triggers, so resets still work.
"""
from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION brightloop_guard_invoice() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status <> 'draft' THEN
      RAISE EXCEPTION 'Invoice % is %, it cannot be deleted', OLD.number, OLD.status USING ERRCODE = 'check_violation';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.status = 'draft' THEN
    RETURN NEW;
  END IF;
  IF OLD.status = 'cancelled' AND NEW IS DISTINCT FROM OLD THEN
    RAISE EXCEPTION 'Invoice % is cancelled and cannot change', OLD.number USING ERRCODE = 'check_violation';
  END IF;
  IF (NEW.number, NEW.subscription_id, NEW.customer_id, NEW.customer_snapshot::text, NEW.period_start,
      NEW.period_end, NEW.invoice_date, NEW.due_date, NEW.currency, NEW.subtotal, NEW.discount_total,
      NEW.tax_total, NEW.total, NEW.applied_discounts::text)
     IS DISTINCT FROM
     (OLD.number, OLD.subscription_id, OLD.customer_id, OLD.customer_snapshot::text, OLD.period_start,
      OLD.period_end, OLD.invoice_date, OLD.due_date, OLD.currency, OLD.subtotal, OLD.discount_total,
      OLD.tax_total, OLD.total, OLD.applied_discounts::text) THEN
    RAISE EXCEPTION 'Invoice % is %, its contents are immutable', OLD.number, OLD.status USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.status <> OLD.status AND NOT (
       (OLD.status = 'confirmed' AND NEW.status IN ('paid', 'cancelled'))) THEN
    RAISE EXCEPTION 'Invoice % cannot move from % to %', OLD.number, OLD.status, NEW.status USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION brightloop_guard_invoice_line() RETURNS trigger AS $$
DECLARE
  parent_status text;
BEGIN
  SELECT status INTO parent_status FROM core_invoice WHERE id = COALESCE(NEW.invoice_id, OLD.invoice_id);
  -- Detaching a deleted product or discount (ON DELETE SET NULL) is allowed: the line keeps its snapshot text.
  IF TG_OP = 'UPDATE'
     AND (NEW.invoice_id, NEW.description, NEW.quantity, NEW.unit_price, NEW.subtotal, NEW.discount_name,
          NEW.discount_amount, NEW.taxes::text, NEW.tax_amount, NEW.total)
         IS NOT DISTINCT FROM
         (OLD.invoice_id, OLD.description, OLD.quantity, OLD.unit_price, OLD.subtotal, OLD.discount_name,
          OLD.discount_amount, OLD.taxes::text, OLD.tax_amount, OLD.total)
     AND (NEW.product_id IS NULL OR NEW.product_id = OLD.product_id)
     AND (NEW.discount_id IS NULL OR NEW.discount_id = OLD.discount_id) THEN
    RETURN NEW;
  END IF;
  IF parent_status IS NOT NULL AND parent_status <> 'draft' THEN
    RAISE EXCEPTION 'Lines of a % invoice are immutable', parent_status USING ERRCODE = 'check_violation';
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION brightloop_guard_payment() RETURNS trigger AS $$
BEGIN
  -- Only detaching a deleted user (created_by ON DELETE SET NULL) is allowed.
  IF TG_OP = 'UPDATE' AND NEW.created_by_id IS NULL
     AND (NEW.invoice_id, NEW.method, NEW.amount, NEW.date, NEW.note, NEW.created_at)
         IS NOT DISTINCT FROM (OLD.invoice_id, OLD.method, OLD.amount, OLD.date, OLD.note, OLD.created_at) THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Payments are append-only: record a refund instead of changing payment %', OLD.id
    USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER brightloop_invoice_guard BEFORE UPDATE OR DELETE ON core_invoice
  FOR EACH ROW EXECUTE FUNCTION brightloop_guard_invoice();
CREATE TRIGGER brightloop_invoice_line_guard BEFORE UPDATE OR DELETE ON core_invoiceline
  FOR EACH ROW EXECUTE FUNCTION brightloop_guard_invoice_line();
CREATE TRIGGER brightloop_payment_guard BEFORE UPDATE OR DELETE ON core_payment
  FOR EACH ROW EXECUTE FUNCTION brightloop_guard_payment();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS brightloop_payment_guard ON core_payment;
DROP TRIGGER IF EXISTS brightloop_invoice_line_guard ON core_invoiceline;
DROP TRIGGER IF EXISTS brightloop_invoice_guard ON core_invoice;
DROP FUNCTION IF EXISTS brightloop_guard_payment();
DROP FUNCTION IF EXISTS brightloop_guard_invoice_line();
DROP FUNCTION IF EXISTS brightloop_guard_invoice();
"""


def _run(sql):
    def apply(apps, schema_editor):
        if schema_editor.connection.vendor == "postgresql":
            with schema_editor.connection.cursor() as cur:
                cur.execute(sql)  # no params: the % in RAISE messages must not be treated as placeholders

    return apply


class Migration(migrations.Migration):
    dependencies = [("core", "0004_money_check_constraints")]
    operations = [migrations.RunPython(_run(FORWARD), _run(REVERSE))]
