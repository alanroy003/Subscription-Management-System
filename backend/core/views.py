from datetime import date

from django.db import connection, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Prefetch, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response

from . import audit, reports, services
from .models import (
    AuditEvent,
    BillingRun,
    Customer,
    Discount,
    IntegrityCheck,
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
from .permissions import IsAdmin, IsTeam, TeamReadAdminWrite
from .serializers import (
    AuditEventSerializer,
    BillingRunSerializer,
    CustomerSerializer,
    DiscountSerializer,
    IntegrityCheckSerializer,
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


@extend_schema(tags=["health"], summary="Health check", responses=inline_serializer(
    "Health", {"status": serializers.CharField(), "database": serializers.CharField()}))
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    with connection.cursor() as cur:
        cur.execute("select 1")
    return Response({"status": "ok", "database": connection.vendor})


@extend_schema(tags=["payment-terms"], summary="Payment terms", responses=inline_serializer(
    "PaymentTerm", {"days": serializers.IntegerField(), "label": serializers.CharField()}, many=True))
@api_view(["GET"])
@permission_classes([AllowAny])
def payment_terms(request):
    return Response([{"days": 0, "label": "Immediate"}, {"days": 15, "label": "Net 15"},
                     {"days": 30, "label": "Net 30"}, {"days": 45, "label": "Net 45"}])


class TaxGroupViewSet(audit.AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = TaxGroup.objects.order_by("name")
    serializer_class = TaxGroupSerializer
    permission_classes = [TeamReadAdminWrite]
    search_fields = ["name"]


class ProductViewSet(audit.AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Product.objects.select_related("tax_group").prefetch_related("variants")
    serializer_class = ProductSerializer
    permission_classes = [TeamReadAdminWrite]
    search_fields = ["name", "notes"]


class PlanViewSet(audit.AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Plan.objects.select_related("product")
    serializer_class = PlanSerializer
    permission_classes = [TeamReadAdminWrite]
    search_fields = ["name"]


class DiscountViewSet(audit.AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Discount.objects.prefetch_related("products").order_by("-id")
    serializer_class = DiscountSerializer
    permission_classes = [TeamReadAdminWrite]
    search_fields = ["name"]


class QuotationTemplateViewSet(audit.AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = QuotationTemplate.objects.select_related("plan").prefetch_related("lines__product").order_by("name")
    serializer_class = QuotationTemplateSerializer
    permission_classes = [IsTeam]
    search_fields = ["name"]


class CustomerViewSet(audit.AuditedModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Customer.objects.all()
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


class SubscriptionViewSet(audit.AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = SubscriptionSerializer
    queryset = Subscription.objects.all()
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
        with transaction.atomic():
            sub = serializer.save(created_by=self.request.user)
            audit.record("subscription.created", sub, changes={"customer": sub.customer_id, "plan": sub.plan_id})

    def destroy(self, request, *args, **kwargs):
        sub = self.get_object()
        if sub.status != Subscription.Status.DRAFT:
            raise ValidationError({"detail": "Only draft subscriptions can be deleted."})
        return super().destroy(request, *args, **kwargs)

    @extend_schema(summary="Create a quotation from a template", request=inline_serializer("FromTemplate", {
        "template": serializers.IntegerField(), "customer": serializers.IntegerField(),
        "start_date": serializers.DateField(required=False),
        "payment_term_days": serializers.IntegerField(required=False)}), responses={201: SubscriptionSerializer})
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
        audit.record("subscription.created", sub, changes={"template": tpl.name, "customer": customer.pk})
        _domain(lambda: services.transition(sub, "send_quotation", request.user))
        return Response(self.get_serializer(self.get_queryset().get(pk=sub.pk)).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Move a subscription through its lifecycle",
        description="Allowed actions depend on the status, the plan options and the caller's role; see "
                    "`available_actions` on the subscription.",
        request=inline_serializer("Transition", {
            "action": serializers.ChoiceField(
                choices=["send_quotation", "confirm", "activate", "pause", "resume", "close", "renew"]),
            "note": serializers.CharField(required=False)}),
        responses={200: SubscriptionSerializer},
    )
    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        # Ownership check without the detail prefetches; customers only reach their own subscriptions.
        sub = get_object_or_404(self.filter_queryset(Subscription.objects.filter(
            pk=pk, **({} if request.user.is_team else {"customer__user": request.user}))))
        act = request.data.get("action", "")
        _domain(lambda: services.transition(sub, act, request.user, request.data.get("note", "")))
        return Response(self.get_serializer(self.get_queryset().get(pk=sub.pk)).data)


class PdfRenderer(BaseRenderer):
    """Lets clients ask for `Accept: application/pdf` on the PDF download."""

    media_type = "application/pdf"
    format = "pdf"
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if isinstance(data, bytes | bytearray):
            return data
        import json  # an error payload (403, 404) is still sent as readable JSON

        if renderer_context and renderer_context.get("response") is not None:
            renderer_context["response"]["Content-Type"] = "application/json"
        return json.dumps(data).encode()


class InvoiceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Invoice.objects.all()
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

    @extend_schema(
        summary="Download the invoice as a PDF",
        description="Rendered from the invoice's stored snapshot. Add `?inline=1` to open it in the browser instead "
                    "of downloading. Customers can download their own issued invoices.",
        parameters=[OpenApiParameter("inline", OpenApiTypes.BOOL)],
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    @action(detail=True, methods=["get"], renderer_classes=[JSONRenderer, PdfRenderer])
    def pdf(self, request, pk=None):
        from django.http import HttpResponse

        from .pdf import PdfError, invoice_filename, render_invoice_pdf

        invoice = self.get_object()  # customers only reach their own, non-draft invoices
        try:
            data = render_invoice_pdf(invoice)
        except PdfError as exc:
            raise ValidationError({"detail": str(exc)})
        disposition = "inline" if request.query_params.get("inline") in ("1", "true") else "attachment"
        response = HttpResponse(data, content_type="application/pdf")
        response["Content-Disposition"] = f'{disposition}; filename="{invoice_filename(invoice)}"'
        return response

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

    @extend_schema(
        summary="Confirm several draft invoices",
        request=inline_serializer("BulkConfirm", {"ids": serializers.ListField(child=serializers.IntegerField())}),
        responses=inline_serializer("BulkConfirmed", {"confirmed": serializers.IntegerField()}),
    )
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
    queryset = Payment.objects.all()
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

    @extend_schema(summary="Run billing (or a dry run)", request=inline_serializer("BillingRunRequest", {
        "as_of": serializers.DateField(required=False), "dry_run": serializers.BooleanField(default=False)}),
        responses=BillingRunSerializer)
    @action(detail=False, methods=["post"])
    def run(self, request):
        as_of = request.data.get("as_of") or None
        if as_of:
            as_of = date.fromisoformat(as_of)
        run = services.run_billing(as_of, bool(request.data.get("dry_run")), request.user)
        return Response(BillingRunSerializer(run).data)


@extend_schema(
    tags=["reports"], summary="Finance summary",
    description="Active subscriptions, billed, collected, outstanding and overdue amounts, MRR, ARPU, churn, "
                "monthly revenue series, renewals and 30/60/90-day cash forecast, at-risk customers.",
    parameters=[OpenApiParameter("date_from", OpenApiTypes.DATE), OpenApiParameter("date_to", OpenApiTypes.DATE)],
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET"])
@permission_classes([IsTeam])
def report_summary(request):
    p = request.query_params
    d_from = date.fromisoformat(p["date_from"]) if p.get("date_from") else None
    d_to = date.fromisoformat(p["date_to"]) if p.get("date_to") else None
    return Response(reports.summary(d_from, d_to))


class IntegrityCheckViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Reconciliation runs: the team can read them, the admin can start one."""

    queryset = IntegrityCheck.objects.all()
    serializer_class = IntegrityCheckSerializer
    permission_classes = [IsTeam]

    @extend_schema(summary="Run a reconciliation check now", request=None, responses=IntegrityCheckSerializer)
    @action(detail=False, methods=["post"], permission_classes=[IsAdmin])
    def run(self, request):
        from .integrity import run_check

        check = run_check(notify=False, user=request.user)
        audit.record("integrity.check", check, ref=f"{check.issue_count} issue(s)")
        return Response(IntegrityCheckSerializer(check).data)


class AuditEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only audit log for admins. Filters: `action` (prefix, e.g. `invoice.`), `actor`, `object_type`,
    `object_id`, `via`, `date_from`, `date_to`; `search` matches the reference, actor email and action."""

    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventSerializer
    permission_classes = [IsAdmin]
    search_fields = ["object_ref", "actor_label", "action"]

    def get_queryset(self):
        qs = AuditEvent.objects.all()
        p = self.request.query_params
        if p.get("action"):
            qs = qs.filter(action__startswith=p["action"])
        for key in ("actor", "object_type", "object_id", "via"):
            if p.get(key):
                qs = qs.filter(**{key: p[key]})
        if p.get("date_from"):
            qs = qs.filter(at__date__gte=p["date_from"])
        if p.get("date_to"):
            qs = qs.filter(at__date__lte=p["date_to"])
        return qs
