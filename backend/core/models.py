from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models

from .money import ZERO

MONEY = {"max_digits": 14, "decimal_places": 2, "default": ZERO}


def check(name: str, condition: models.Q) -> models.CheckConstraint:
    """A database-level rule: the row is rejected by Postgres (and SQLite) if `condition` is false."""
    return models.CheckConstraint(condition=condition, name=name)


Q, F = models.Q, models.F


class Customer(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    state = models.CharField(max_length=80, blank=True, help_text="Place of supply for GST")
    gstin = models.CharField(max_length=20, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="customer"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TaxGroup(models.Model):
    class Mode(models.TextChoices):
        GST = "gst", "GST (CGST+SGST or IGST)"
        SIMPLE = "simple", "Single tax"

    name = models.CharField(max_length=100)
    rate = models.DecimalField(max_digits=6, decimal_places=3, help_text="Total rate in percent")
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.GST)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    class Type(models.TextChoices):
        SOFTWARE = "software", "Software"
        SERVICE = "service", "Service"
        GOODS = "goods", "Goods"

    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SOFTWARE)
    sales_price = models.DecimalField(**MONEY)
    cost_price = models.DecimalField(**MONEY)
    notes = models.TextField(blank=True)
    tax_group = models.ForeignKey(TaxGroup, null=True, blank=True, on_delete=models.SET_NULL)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [check("product_prices_not_negative", Q(sales_price__gte=0, cost_price__gte=0))]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute = models.CharField(max_length=80, help_text="e.g. Brand")
    value = models.CharField(max_length=80, help_text="e.g. Odoo")
    price_extra = models.DecimalField(**MONEY)

    @property
    def price(self) -> Decimal:
        return self.product.sales_price + self.price_extra

    @property
    def label(self) -> str:
        return f"{self.attribute}: {self.value}"


class Plan(models.Model):
    class Period(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    name = models.CharField(max_length=200)
    product = models.ForeignKey(
        Product, null=True, blank=True, on_delete=models.SET_NULL, help_text="Base product billed by this plan"
    )
    price = models.DecimalField(**MONEY)
    billing_period = models.CharField(max_length=10, choices=Period.choices, default=Period.MONTHLY)
    min_quantity = models.PositiveIntegerField(default=1)
    available_from = models.DateField(null=True, blank=True)
    available_to = models.DateField(null=True, blank=True)
    auto_close = models.BooleanField(default=False)
    closable = models.BooleanField(default=True)
    pausable = models.BooleanField(default=False)
    renewable = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            check("plan_price_not_negative", Q(price__gte=0)),
            check(
                "plan_availability_in_order",
                Q(available_from__isnull=True)
                | Q(available_to__isnull=True)
                | Q(available_to__gte=F("available_from")),
            ),
        ]

    def __str__(self):
        return self.name

    def is_available_on(self, day: date) -> bool:
        return (self.available_from is None or self.available_from <= day) and (
            self.available_to is None or day <= self.available_to
        )


class Discount(models.Model):
    class Kind(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENT = "percent", "Percentage"

    class Scope(models.TextChoices):
        ALL = "all", "Whole subscription"
        PRODUCTS = "products", "Specific products"

    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    value = models.DecimalField(max_digits=14, decimal_places=2)
    min_amount = models.DecimalField(**MONEY)
    min_quantity = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    scope = models.CharField(max_length=10, choices=Scope.choices, default=Scope.ALL)
    products = models.ManyToManyField(Product, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            check("discount_value_positive", Q(value__gt=0)),
            check("discount_percent_at_most_100", ~Q(kind="percent") | Q(value__lte=100)),
            check("discount_min_amount_not_negative", Q(min_amount__gte=0)),
            check("discount_dates_in_order",
                  Q(start_date__isnull=True) | Q(end_date__isnull=True) | Q(end_date__gte=F("start_date"))),
            check("discount_usage_within_limit", Q(usage_limit__isnull=True) | Q(used_count__lte=F("usage_limit"))),
        ]

    def __str__(self):
        return self.name


class QuotationTemplate(models.Model):
    name = models.CharField(max_length=150)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    validity_days = models.PositiveIntegerField(default=30)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class QuotationTemplateLine(models.Model):
    template = models.ForeignKey(QuotationTemplate, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1)


class Subscription(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUOTATION = "quotation", "Quotation"
        CONFIRMED = "confirmed", "Confirmed"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"

    number = models.CharField(max_length=30, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    template = models.ForeignKey(QuotationTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    start_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    next_invoice_date = models.DateField(null=True, blank=True, db_index=True)
    payment_term_days = models.PositiveIntegerField(default=15)
    quotation_valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    closed_at = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["status", "next_invoice_date"]), models.Index(fields=["customer", "status"])]

    def __str__(self):
        return self.number


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    tax_group = models.ForeignKey(TaxGroup, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [check("subscription_line_valid", Q(quantity__gte=1, unit_price__gte=0))]

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


class SubscriptionEvent(models.Model):
    """Timeline and audit trail of subscription state changes."""

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.CharField(max_length=255, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at", "id"]


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=30, unique=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="invoices")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    customer_snapshot = models.JSONField(default=dict)
    period_start = models.DateField()
    period_end = models.DateField()
    invoice_date = models.DateField(db_index=True)
    due_date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    currency = models.CharField(max_length=3, default="INR")
    subtotal = models.DecimalField(**MONEY)
    discount_total = models.DecimalField(**MONEY)
    tax_total = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)
    amount_paid = models.DecimalField(**MONEY)
    applied_discounts = models.JSONField(default=list, help_text="Discount ids counted against usage limits")
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        constraints = [
            # The core billing invariant: one invoice per subscription per period.
            models.UniqueConstraint(fields=["subscription", "period_start"], name="uniq_invoice_subscription_period"),
            check("invoice_amounts_not_negative",
                  Q(subtotal__gte=0, discount_total__gte=0, tax_total__gte=0, total__gte=0, amount_paid__gte=0)),
            check("invoice_paid_within_total", Q(amount_paid__lte=F("total"))),
            check("invoice_discount_within_subtotal", Q(discount_total__lte=F("subtotal"))),
            check("invoice_total_adds_up", Q(total=F("subtotal") - F("discount_total") + F("tax_total"))),
            check("invoice_period_in_order", Q(period_end__gte=F("period_start"))),
            check("invoice_due_after_issue", Q(due_date__gte=F("invoice_date"))),
            check("invoice_paid_means_settled", ~Q(status="paid") | Q(amount_paid=F("total"))),
        ]
        indexes = [models.Index(fields=["status", "due_date"]), models.Index(fields=["customer", "status"])]

    @property
    def balance(self) -> Decimal:
        return self.total - self.amount_paid

    @property
    def is_overdue(self) -> bool:
        return self.status == self.Status.CONFIRMED and self.due_date < date.today() and self.balance > 0


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    subtotal = models.DecimalField(**MONEY)
    discount = models.ForeignKey(Discount, null=True, blank=True, on_delete=models.SET_NULL)
    discount_name = models.CharField(max_length=150, blank=True)
    discount_amount = models.DecimalField(**MONEY)
    taxes = models.JSONField(default=list, help_text="Snapshot: [{name, rate, amount}]")
    tax_amount = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)

    class Meta:
        constraints = [
            check("invoice_line_amounts_valid",
                  Q(quantity__gte=1, unit_price__gte=0, subtotal__gte=0, discount_amount__gte=0, tax_amount__gte=0)),
            check("invoice_line_discount_within_subtotal", Q(discount_amount__lte=F("subtotal"))),
            check("invoice_line_total_adds_up", Q(total=F("subtotal") - F("discount_amount") + F("tax_amount"))),
        ]


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank_transfer", "Bank transfer"
        UPI = "upi", "UPI"
        CARD = "card", "Card"
        CHEQUE = "cheque", "Cheque"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=20, choices=Method.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField(db_index=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [check("payment_amount_positive", Q(amount__gt=0))]


class BillingRun(models.Model):
    run_date = models.DateField()
    dry_run = models.BooleanField(default=False)
    created = models.PositiveIntegerField(default=0)
    skipped = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    items = models.JSONField(default=list)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-id"]


class IntegrityCheck(models.Model):
    """One reconciliation run (see core/integrity.py)."""

    started_at = models.DateTimeField()
    finished_at = models.DateTimeField()
    issue_count = models.PositiveIntegerField(default=0)
    issues = models.JSONField(default=list)
    counts = models.JSONField(default=dict)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-id"]


class Sequence(models.Model):
    """Gap-free document numbering, locked with SELECT ... FOR UPDATE."""

    key = models.CharField(max_length=30, unique=True)
    value = models.PositiveIntegerField(default=0)
