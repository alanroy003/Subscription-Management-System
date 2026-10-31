from django.db import transaction
from rest_framework import serializers

from .models import (
    AuditEvent,
    BillingRun,
    Customer,
    Discount,
    IntegrityCheck,
    Invoice,
    InvoiceLine,
    Payment,
    Plan,
    Product,
    ProductVariant,
    QuotationTemplate,
    QuotationTemplateLine,
    Subscription,
    SubscriptionEvent,
    SubscriptionLine,
    TaxGroup,
)
from .money import ZERO
from .pricing import default_unit_price
from .services import available_actions


class TaxGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxGroup
        fields = ["id", "name", "rate", "mode", "is_active"]


class VariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = ProductVariant
        fields = ["id", "attribute", "value", "price_extra", "price"]


class ProductSerializer(serializers.ModelSerializer):
    variants = VariantSerializer(many=True, required=False)
    tax_group_name = serializers.CharField(source="tax_group.name", read_only=True, default="")

    class Meta:
        model = Product
        fields = ["id", "name", "type", "sales_price", "cost_price", "notes", "tax_group", "tax_group_name",
                  "is_active", "variants"]

    def validate(self, attrs):
        for f in ("sales_price", "cost_price"):
            if attrs.get(f) is not None and attrs[f] < 0:
                raise serializers.ValidationError({f: "Must not be negative."})
        return attrs

    @transaction.atomic
    def create(self, data):
        variants = data.pop("variants", [])
        product = Product.objects.create(**data)
        for v in variants:
            v.pop("id", None)
            ProductVariant.objects.create(product=product, **v)
        return product

    @transaction.atomic
    def update(self, product, data):
        variants = data.pop("variants", None)
        product = super().update(product, data)
        if variants is not None:
            keep = []
            for v in variants:
                vid = v.pop("id", None)
                obj = product.variants.filter(pk=vid).first() if vid else None
                if obj:
                    for k, val in v.items():
                        setattr(obj, k, val)
                    obj.save()
                else:
                    obj = ProductVariant.objects.create(product=product, **v)
                keep.append(obj.pk)
            product.variants.exclude(pk__in=keep).delete()
        return product


class PlanSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default="")
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = ["id", "name", "product", "product_name", "price", "billing_period", "min_quantity", "available_from",
                  "available_to", "auto_close", "closable", "pausable", "renewable", "is_available"]

    def get_is_available(self, plan) -> bool:
        from datetime import date
        return plan.is_available_on(date.today())

    def validate(self, attrs):
        start = attrs.get("available_from", getattr(self.instance, "available_from", None))
        end = attrs.get("available_to", getattr(self.instance, "available_to", None))
        if start and end and end < start:
            raise serializers.ValidationError({"available_to": "Must be on or after the start date."})
        if attrs.get("price") is not None and attrs["price"] < 0:
            raise serializers.ValidationError({"price": "Must not be negative."})
        return attrs


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = ["id", "name", "kind", "value", "min_amount", "min_quantity", "start_date", "end_date",
                  "usage_limit", "used_count", "scope", "products", "is_active"]
        read_only_fields = ["used_count"]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        value = attrs.get("value", getattr(self.instance, "value", None))
        if value is not None and value <= 0:
            raise serializers.ValidationError({"value": "Must be positive."})
        if kind == "percent" and value is not None and value > 100:
            raise serializers.ValidationError({"value": "A percentage cannot exceed 100."})
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "Must be on or after the start date."})
        limit = attrs.get("usage_limit", getattr(self.instance, "usage_limit", None))
        used = self.instance.used_count if self.instance else 0
        if limit is not None and limit < used:
            raise serializers.ValidationError({"usage_limit": f"Already used {used} times; the limit cannot be lower."})
        return attrs


class CustomerSerializer(serializers.ModelSerializer):
    has_login = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ["id", "name", "email", "phone", "address", "state", "gstin", "has_login"]

    def get_has_login(self, c) -> bool:
        return c.user_id is not None


class TemplateLineSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = QuotationTemplateLine
        fields = ["id", "product", "product_name", "variant", "quantity"]


class QuotationTemplateSerializer(serializers.ModelSerializer):
    lines = TemplateLineSerializer(many=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = QuotationTemplate
        fields = ["id", "name", "plan", "plan_name", "validity_days", "notes", "lines"]

    @transaction.atomic
    def create(self, data):
        lines = data.pop("lines", [])
        tpl = QuotationTemplate.objects.create(**data)
        for l in lines:
            l.pop("id", None)
            QuotationTemplateLine.objects.create(template=tpl, **l)
        return tpl

    @transaction.atomic
    def update(self, tpl, data):
        lines = data.pop("lines", None)
        tpl = super().update(tpl, data)
        if lines is not None:
            tpl.lines.all().delete()
            for l in lines:
                l.pop("id", None)
                QuotationTemplateLine.objects.create(template=tpl, **l)
        return tpl


class SubscriptionLineSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    product_name = serializers.CharField(source="product.name", read_only=True)
    variant_label = serializers.SerializerMethodField()
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)

    class Meta:
        model = SubscriptionLine
        fields = ["id", "product", "product_name", "variant", "variant_label", "description", "quantity",
                  "unit_price", "tax_group", "subtotal"]

    def get_variant_label(self, line) -> str:
        return line.variant.label if line.variant else ""

    def validate(self, attrs):
        variant = attrs.get("variant")
        if variant and variant.product_id != attrs["product"].id:
            raise serializers.ValidationError({"variant": "Variant does not belong to the product."})
        if attrs.get("quantity", 1) < 1:
            raise serializers.ValidationError({"quantity": "Must be at least 1."})
        return attrs


class EventSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionEvent
        fields = ["at", "from_status", "to_status", "user_name", "note"]

    def get_user_name(self, e) -> str:
        return (e.user.name or e.user.email) if e.user else "System"


EDITABLE = (Subscription.Status.DRAFT, Subscription.Status.QUOTATION)


def build_lines(sub: Subscription, lines: list[dict]) -> None:
    sub.lines.all().delete()
    for l in lines:
        l.pop("id", None)
        if l.get("unit_price") is None:
            l["unit_price"] = default_unit_price(sub.plan, l["product"], l.get("variant"))
        if "tax_group" not in l or l["tax_group"] is None:
            l["tax_group"] = l["product"].tax_group
        SubscriptionLine.objects.create(subscription=sub, **l)


class SubscriptionSerializer(serializers.ModelSerializer):
    lines = SubscriptionLineSerializer(many=True, required=False)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    billing_period = serializers.CharField(source="plan.billing_period", read_only=True)
    subtotal = serializers.SerializerMethodField()
    recurring_total = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()
    events = EventSerializer(many=True, read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "number", "customer", "customer_name", "plan", "plan_name", "billing_period", "status",
                  "start_date", "expiry_date", "next_invoice_date", "payment_term_days", "quotation_valid_until",
                  "notes", "lines", "subtotal", "recurring_total", "available_actions", "events", "created_at"]
        read_only_fields = ["number", "status", "next_invoice_date", "quotation_valid_until"]

    def get_subtotal(self, sub) -> str:
        return str(sum((l.subtotal for l in sub.lines.all()), ZERO))

    get_recurring_total = get_subtotal

    def get_available_actions(self, sub) -> list[str]:
        request = self.context.get("request")
        return available_actions(sub, request.user) if request else []

    def validate(self, attrs):
        if self.instance and self.instance.status not in EDITABLE:
            raise serializers.ValidationError("Only draft or quotation subscriptions can be edited.")
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        expiry = attrs.get("expiry_date", getattr(self.instance, "expiry_date", None))
        if start and expiry and expiry <= start:
            raise serializers.ValidationError({"expiry_date": "Must be after the start date."})
        return attrs

    @transaction.atomic
    def create(self, data):
        from .services import next_number
        lines = data.pop("lines", [])
        sub = Subscription.objects.create(number=next_number("SUB"), **data)
        build_lines(sub, lines)
        from .services import _log
        _log(sub, "", data.get("created_by"), "Created")
        return sub

    @transaction.atomic
    def update(self, sub, data):
        lines = data.pop("lines", None)
        sub = super().update(sub, data)
        if lines is not None:
            build_lines(sub, lines)
        return sub


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    customer_name = serializers.CharField(source="invoice.customer.name", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "invoice", "invoice_number", "customer_name", "method", "amount", "date", "note", "created_at"]


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = ["description", "quantity", "unit_price", "subtotal", "discount_name", "discount_amount", "taxes",
                  "tax_amount", "total"]


class InvoiceListSerializer(serializers.ModelSerializer):
    subscription_number = serializers.CharField(source="subscription.number", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = ["id", "number", "subscription", "subscription_number", "customer", "customer_name", "period_start",
                  "period_end", "invoice_date", "due_date", "status", "currency", "subtotal", "discount_total",
                  "tax_total", "total", "amount_paid", "balance", "is_overdue", "sent_at"]


class InvoiceSerializer(InvoiceListSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    company = serializers.SerializerMethodField()

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + ["customer_snapshot", "lines", "payments", "company"]

    def get_company(self, _) -> dict:
        from django.conf import settings
        return settings.COMPANY


class BillingRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingRun
        fields = ["id", "run_date", "dry_run", "created", "skipped", "failed", "items", "started_at", "finished_at"]


class SubscriptionListSerializer(serializers.ModelSerializer):
    """List rows: no nested lines or events (the amount is a SQL annotation), so a page is two queries."""

    customer_name = serializers.CharField(source="customer.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    billing_period = serializers.CharField(source="plan.billing_period", read_only=True)
    recurring_total = serializers.DecimalField(source="amount", max_digits=16, decimal_places=2, read_only=True)
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ["id", "number", "customer", "customer_name", "plan", "plan_name", "billing_period", "status",
                  "start_date", "expiry_date", "next_invoice_date", "payment_term_days", "quotation_valid_until",
                  "recurring_total", "available_actions", "created_at"]

    def get_available_actions(self, sub) -> list[str]:
        request = self.context.get("request")
        return available_actions(sub, request.user) if request else []


class IntegrityCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrityCheck
        fields = ["id", "started_at", "finished_at", "issue_count", "issues", "counts"]


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = ["id", "at", "action", "actor", "actor_label", "via", "api_key_prefix", "object_type", "object_id",
                  "object_ref", "changes", "ip"]


class UpcomingRenewalSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    renewable = serializers.BooleanField(source="plan.renewable", read_only=True)
    days_left = serializers.SerializerMethodField()
    reminders_sent = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ["id", "number", "customer", "customer_name", "customer_email", "plan_name", "status", "expiry_date",
                  "days_left", "renewable", "reminders_sent"]

    def get_days_left(self, sub) -> int:
        from datetime import date

        return (sub.expiry_date - date.today()).days

    def get_reminders_sent(self, sub) -> list[int]:
        """Thresholds already sent for the current expiry date, e.g. [30, 7]."""
        return sorted((r.days_before for r in sub.renewal_reminders.all() if r.expiry_date == sub.expiry_date),
                      reverse=True)
