"""Public API keys: hashed at rest, scoped (read / write), revocable, rate limited, with idempotent POSTs.

A key looks like `bl_<prefix>_<secret>`. Only `sha256(pepper + key)` is stored; the full key is shown once at creation.
Requests send `X-API-Key: <key>` and act as the admin who created the key, limited by the key's scopes.
"""
import hashlib
import os
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from rest_framework import authentication, exceptions, permissions, throttling

SCOPES = ("read", "write")


def _hash(raw: str) -> str:
    pepper = os.environ.get("API_KEY_PEPPER", settings.SECRET_KEY)
    return hashlib.sha256(f"{pepper}{raw}".encode()).hexdigest()


class ApiKey(models.Model):
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=12, unique=True)
    key_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "accounts"
        ordering = ["-id"]

    @classmethod
    def issue(cls, name: str, scopes: list[str], user) -> tuple["ApiKey", str]:
        prefix = secrets.token_hex(4)
        raw = f"bl_{prefix}_{secrets.token_urlsafe(32)}"
        key = cls.objects.create(name=name, prefix=prefix, key_hash=_hash(raw), scopes=scopes, created_by=user)
        return key, raw


class IdempotencyRecord(models.Model):
    """Stored response for a POST made with an `Idempotency-Key` header, replayed on retries."""

    api_key = models.ForeignKey(ApiKey, on_delete=models.CASCADE)
    key = models.CharField(max_length=100)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=300)
    status_code = models.PositiveIntegerField()
    body = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "accounts"
        constraints = [models.UniqueConstraint(fields=["api_key", "key"], name="uniq_idempotency_key")]


class ApiKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        raw = request.META.get("HTTP_X_API_KEY")
        if not raw:
            return None
        key = ApiKey.objects.select_related("created_by").filter(key_hash=_hash(raw), revoked_at__isnull=True).first()
        if not key or not key.created_by.is_active:
            raise exceptions.AuthenticationFailed("Invalid or revoked API key.")
        needed = "read" if request.method in permissions.SAFE_METHODS else "write"
        if needed not in key.scopes:
            raise exceptions.PermissionDenied(f"This API key does not have the '{needed}' scope.")
        ApiKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return key.created_by, key

    def authenticate_header(self, request):
        return "X-API-Key"


class ApiKeyThrottle(throttling.SimpleRateThrottle):
    scope = "api_key"
    rate = os.environ.get("API_KEY_RATE", "120/min")

    def get_cache_key(self, request, view):
        if not isinstance(request.auth, ApiKey):
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.auth.prefix}


class IdempotencyMiddleware:
    """Replays the stored response when a POST with the same `Idempotency-Key` is retried with the same API key."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        idem = request.META.get("HTTP_IDEMPOTENCY_KEY", "")[:100]
        raw = request.META.get("HTTP_X_API_KEY")
        if request.method != "POST" or not idem or not raw:
            return self.get_response(request)
        import json

        from django.db import IntegrityError
        from django.http import JsonResponse

        key = ApiKey.objects.filter(key_hash=_hash(raw), revoked_at__isnull=True).first()
        if key is None:
            return self.get_response(request)
        seen = IdempotencyRecord.objects.filter(api_key=key, key=idem).first()
        if seen:
            if seen.path != request.path:
                return JsonResponse({"detail": "Idempotency-Key was already used for a different request."}, status=422)
            response = JsonResponse(seen.body, status=seen.status_code, safe=False)
            response["Idempotent-Replayed"] = "true"
            return response
        response = self.get_response(request)
        if response.status_code < 500 and response.get("Content-Type", "").startswith("application/json"):
            try:
                IdempotencyRecord.objects.create(api_key=key, key=idem, method="POST", path=request.path,
                                                 status_code=response.status_code,
                                                 body=json.loads(response.content or b"null"))
            except IntegrityError:
                pass  # a concurrent retry stored it first
        return response
