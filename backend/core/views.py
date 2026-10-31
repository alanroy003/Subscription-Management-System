from datetime import date

from django.db import connection
from django.db.models import DecimalField, ExpressionWrapper, F, Prefetch, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import reports, services
from .models import (
    BillingRun,
    Customer,
    Discount,
    Invoice,
    Payment,
    Plan,
    Product,
    QuotationTemplate,
    Subscription,
    SubscriptionLine,
    TaxGroup,
)
from .money import ZERO
from .permissions import IsTeam, TeamReadAdminWrite
from .serializers import (
    BillingRunSerializer,
    CustomerSerializer,
    DiscountSerializer,
    InvoiceListSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    PlanSerializer,
    ProductSerializer,
    QuotationTemplateSerializer,
    SubscriptionListSerializer,
    SubscriptionSerializer,
    TaxGroupSerializer,
    build_lines,
)
from .services import DomainError


def _domain(fn):
    """Turn business-rule violations into 400 responses."""
    try:
        return fn()
    except DomainError as exc:
        raise ValidationError({"detail": str(exc)})


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    with connection.cursor() as cur:
        cur.execute("select 1")
    return Response({"status": "ok", "database": connection.vendor})


@api_view(["GET"])
@permission_classes([AllowAny])
def payment_terms(request):
    return Response([{"days": 0, "label": "Immediate"}, {"days": 15, "label": "Net 15"},
                     {"days": 30, "label": "Net 30"}, {"days": 45, "label": "Net 45"}])


class TaxGroupViewSet(viewsets.ModelViewSet):
    queryset = TaxGroup.objects.order_by("name")
    serializer_class = TaxGroupSerializer
    permission_classes = [TeamReadAdminWrite]
    search_fields = ["name"]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related("tax_group").prefetch_related("variants")
    serializer_class = ProductSerializer
    permission_classes = [TeamReadAdminWrite]
    search_fields = ["name", "notes"]


class PlanViewSet(viewsets.ModelViewSet):
    queryset = Plan.objects.select_related("product")
    serializer_class = PlanSerializer
    permission_classes = [TeamReadAdminWrite]
    search_fields = ["name"]


class DiscountViewSet(viewsets.ModelViewSet):
    queryset = Discount.objects.prefetch_related("products").order_by("-id")
    serializer_class = DiscountSerializer
    permission_classes = [TeamReadAdminWrite]
    search_fields = ["name"]


class QuotationTemplateViewSet(viewsets.ModelViewSet):
    queryset = QuotationTemplate.objects.select_related("plan").prefetch_related("lines__product").order_by("name")
    serializer_class = QuotationTemplateSerializer
    permission_classes = [IsTeam]
    search_fields = ["name"]


class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    search_fields = ["name", "email", "gstin"]

    def get_queryset(self):
        qs = Customer.objects.all()
        user = self.request.user
        return qs if user.is_team else qs.filter(user=user)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return super().get_permissions()
        return [IsTeam()]


class SubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    search_fields = ["number", "customer__name", "plan__name"]
    ordering_fields = ["number", "start_date", "next_invoice_date", "created_at"]

    def get_serializer_class(self):
        return SubscriptionListSerializer if self.action == "list" else SubscriptionSerializer

    def get_queryset(self):
        qs = Subscription.objects.select_related("customer", "plan")
        if self.action == "list":
            amount = ExpressionWrapper(F("lines__unit_price") * F("lines__quantity"),
                                       output_field=DecimalField(max_digits=16, decimal_places=2))
            qs = qs.annotate(
                amount=Coalesce(Sum(amount), Value(ZERO), output_field=DecimalField(max_digits=16, decimal_places=2))
            ).order_by("-id")
        else:
            qs = qs.prefetch_related(
                Prefetch("lines", queryset=SubscriptionLine.objects.select_related("product", "variant")),
                "events__user",
            )
        user = self.request.user
        if not user.is_team:
            qs = qs.filter(customer__user=user)
        params = self.request.query_params
        for key in ("status", "customer", "plan"):
            if params.get(key):
                qs = qs.filter(**{key: params[key]})
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve", "transition"):
            return super().get_permissions()
        return [IsTeam()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        sub = self.get_object()
        if sub.status != Subscription.Status.DRAFT:
            raise ValidationError({"detail": "Only draft subscriptions can be deleted."})
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="from-template")
    def from_template(self, request):
        tpl = QuotationTemplate.objects.select_related("plan").filter(pk=request.data.get("template")).first()
        customer = Customer.objects.filter(pk=request.data.get("customer")).first()
        if not tpl or not customer:
            raise ValidationError({"detail": "Template and customer are required."})
        start = request.data.get("start_date") or str(date.today())
        sub = Subscription.objects.create(
            number=services.next_number("SUB"), customer=customer, plan=tpl.plan, template=tpl,
            start_date=start, payment_term_days=int(request.data.get("payment_term_days", 15)),
            notes=tpl.notes, created_by=request.user,
        )
        build_lines(sub, [{"product": l.product, "variant": l.variant, "quantity": l.quantity}
                          for l in tpl.lines.select_related("product", "variant")])
        services._log(sub, "", request.user, f"Created from template {tpl.name}")
        _domain(lambda: services.transition(sub, "send_quotation", request.user))
        return Response(self.get_serializer(self.get_queryset().get(pk=sub.pk)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        # Ownership check without the detail prefetches; customers only reach their own subscriptions.
        sub = get_object_or_404(self.filter_queryset(Subscription.objects.filter(
            pk=pk, **({} if request.user.is_team else {"customer__user": request.user}))))
        act = request.data.get("action", "")
        _domain(lambda: services.transition(sub, act, request.user, request.data.get("note", "")))
        return Response(self.get_serializer(self.get_queryset().get(pk=sub.pk)).data)


class InvoiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    search_fields = ["number", "customer__name", "subscription__number"]
    ordering_fields = ["invoice_date", "due_date", "total", "number"]

    def get_serializer_class(self):
        return InvoiceListSerializer if self.action == "list" else InvoiceSerializer

    def get_queryset(self):
        qs = Invoice.objects.select_related("customer", "subscription")
        if self.action != "list":
            qs = qs.prefetch_related("lines", "payments__invoice__customer")
        user = self.request.user
        if not user.is_team:
            qs = qs.filter(customer__user=user).exclude(status=Invoice.Status.DRAFT)
        p = self.request.query_params
        for key in ("status", "customer", "subscription"):
            if p.get(key):
                qs = qs.filter(**{key: p[key]})
        if p.get("overdue") == "true":
            qs = qs.filter(status=Invoice.Status.CONFIRMED, due_date__lt=date.today())
        if p.get("date_from"):
            qs = qs.filter(invoice_date__gte=p["date_from"])
        if p.get("date_to"):
            qs = qs.filter(invoice_date__lte=p["date_to"])
        return qs

    def _act(self, fn):
        if not self.request.user.is_team:
            raise PermissionDenied()
        invoice = self.get_object()
        _domain(lambda: fn(invoice))
        return Response(InvoiceSerializer(self.get_queryset().get(pk=invoice.pk)).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._act(services.confirm_invoice)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._act(services.cancel_invoice)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        return self._act(services.send_invoice)

    @action(detail=False, methods=["post"], url_path="bulk-confirm", permission_classes=[IsTeam])
    def bulk_confirm(self, request):
        done = 0
        for inv in Invoice.objects.filter(pk__in=request.data.get("ids", []), status=Invoice.Status.DRAFT):
            services.confirm_invoice(inv)
            done += 1
        return Response({"confirmed": done})


class PaymentViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    serializer_class = PaymentSerializer
    search_fields = ["invoice__number", "invoice__customer__name", "note"]

    def get_queryset(self):
        qs = Payment.objects.select_related("invoice__customer")
        user = self.request.user
        if not user.is_team:
            qs = qs.filter(invoice__customer__user=user)
        if self.request.query_params.get("invoice"):
            qs = qs.filter(invoice=self.request.query_params["invoice"])
        return qs

    def get_permissions(self):
        return super().get_permissions() if self.action in ("list", "retrieve") else [IsTeam()]

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        payment = _domain(lambda: services.record_payment(d["invoice"], d["method"], d["amount"], d["date"],
                                                          d.get("note", ""), request.user))
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class BillingRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = BillingRun.objects.all()
    serializer_class = BillingRunSerializer
    permission_classes = [IsTeam]

    @action(detail=False, methods=["post"])
    def run(self, request):
        as_of = request.data.get("as_of") or None
        if as_of:
            as_of = date.fromisoformat(as_of)
        run = services.run_billing(as_of, bool(request.data.get("dry_run")), request.user)
        return Response(BillingRunSerializer(run).data)


@api_view(["GET"])
@permission_classes([IsTeam])
def report_summary(request):
    p = request.query_params
    d_from = date.fromisoformat(p["date_from"]) if p.get("date_from") else None
    d_to = date.fromisoformat(p["date_to"]) if p.get("date_to") else None
    return Response(reports.summary(d_from, d_to))
