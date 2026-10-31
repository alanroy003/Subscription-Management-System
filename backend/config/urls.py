from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from accounts import views as auth_views
from core import views

router = DefaultRouter(trailing_slash=False)
router.register("users", auth_views.UserViewSet, basename="user")
router.register("api-keys", auth_views.ApiKeyViewSet)
router.register("tax-groups", views.TaxGroupViewSet)
router.register("products", views.ProductViewSet)
router.register("plans", views.PlanViewSet)
router.register("discounts", views.DiscountViewSet)
router.register("quotation-templates", views.QuotationTemplateViewSet)
router.register("customers", views.CustomerViewSet, basename="customer")
router.register("subscriptions", views.SubscriptionViewSet, basename="subscription")
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("payments", views.PaymentViewSet, basename="payment")
router.register("billing/runs", views.BillingRunViewSet)
router.register("integrity/checks", views.IntegrityCheckViewSet)

api = [
    path("health", views.health),
    path("payment-terms", views.payment_terms),
    path("billing/run", views.BillingRunViewSet.as_view({"post": "run"})),
    path("reports/summary", views.report_summary),
    path("auth/signup", auth_views.signup),
    path("auth/login", auth_views.login),
    path("auth/logout", auth_views.logout),
    path("auth/me", auth_views.me),
    path("auth/password-reset", auth_views.password_reset),
    path("auth/password-reset/confirm", auth_views.password_reset_confirm),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema")),
    path("", include(router.urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api)),
    path("api/v1/", include(api)),  # versioned base path for the public API (same contract)
]
