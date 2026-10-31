"""Django settings. Values come from the repo-root .env (never committed)."""
import os
import sys
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(REPO_DIR / ".env")

TESTING = "pytest" in sys.modules or os.environ.get("APP_TESTING") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "corsheaders",
    "accounts",
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.audit.AuditContextMiddleware",
    "accounts.apikeys.IdempotencyMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"

# Supabase session pooler (port 5432). Tests use SQLite so they run offline.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if TESTING and TEST_DATABASE_URL:
    # Tests on a throwaway local Postgres (CI service or docker). The suite flushes tables, so never a shared DB.
    if "supabase" in TEST_DATABASE_URL:
        raise RuntimeError("TEST_DATABASE_URL must point at a disposable local Postgres, never Supabase.")
    DATABASES = {"default": dj_database_url.parse(TEST_DATABASE_URL, conn_max_age=0)}
elif TESTING or not os.environ.get("DATABASE_URL"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test.sqlite3"}}
else:
    # The pooler is ~200 ms away, so a client-side pool avoids a TLS handshake per request.
    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=0, ssl_require=True)}
    DATABASES["default"].setdefault("OPTIONS", {})["pool"] = {"min_size": 4, "max_size": 12, "timeout": 20}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [{"NAME": "accounts.validators.BrightloopPasswordValidator"}]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [o for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.apikeys.ApiKeyAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": ["accounts.apikeys.ApiKeyThrottle"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.Pagination",
    "DEFAULT_FILTER_BACKENDS": ["rest_framework.filters.SearchFilter", "rest_framework.filters.OrderingFilter"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "COERCE_DECIMAL_TO_STRING": True,
    "EXCEPTION_HANDLER": "core.exceptions.exception_handler",
}

from config import schema as _api_schema  # noqa: E402  (plain module, safe to import from settings)

SPECTACULAR_SETTINGS = {
    "TITLE": "Brightloop Subscription Management API",
    "VERSION": "1.0.0",
    "DESCRIPTION": _api_schema.DESCRIPTION,
    "TAGS": _api_schema.TAGS,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "PREPROCESSING_HOOKS": ["config.schema.only_versioned_paths"],
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "SubscriptionStatusEnum": "core.models.Subscription.Status",
        "InvoiceStatusEnum": "core.models.Invoice.Status",
    },
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True, "deepLinking": True, "filter": True,
                            "displayRequestDuration": True, "docExpansion": "none"},
    "SERVE_INCLUDE_SCHEMA": False,
}

# Email: SMTP when EMAIL_HOST is set (e.g. Mailpit), otherwise files in backend/sent_emails/.
if os.environ.get("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "1025"))
else:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = BASE_DIR / "sent_emails"
DEFAULT_FROM_EMAIL = "billing@brightloop.local"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

# Company settings used for GST place-of-supply and invoices.
COMPANY = {
    "name": "Brightloop Software Pvt Ltd",
    "state": os.environ.get("COMPANY_STATE", "Gujarat"),
    "gstin": "24AABCB1234F1Z5",
    "address": "Infocity, Gandhinagar, Gujarat",
}
