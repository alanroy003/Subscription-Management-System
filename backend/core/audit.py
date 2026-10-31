"""Audit log: who did what, when, from where.

`record()` writes an `AuditEvent` on the current database connection, so inside a transaction the event commits or
rolls back together with the change it describes. The actor, IP and channel (web, API key, system) are taken from the
request being served (set by `AuditContextMiddleware`); management commands and the scheduler record as "system".
"""
import contextvars
from decimal import Decimal

from django.db import models

from .models import AuditEvent

_request: contextvars.ContextVar = contextvars.ContextVar("audit_request", default=None)

# Never copied into the log, whatever model they appear on.
SECRET_FIELDS = {"password", "key_hash", "token", "secret", "last_login"}


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _request.set(request)
        try:
            return self.get_response(request)
        finally:
            _request.reset(token)


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    return ip or None


def _actor_context(actor=None) -> dict:
    request = _request.get()
    ctx = {"actor": None, "actor_label": "", "via": AuditEvent.Via.SYSTEM, "api_key_prefix": "", "ip": None}
    if request is not None:
        ctx["ip"] = _client_ip(request)
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            ctx["actor"] = user
        auth = getattr(request, "auth", None)
        prefix = getattr(auth, "prefix", "")
        if prefix:  # an ApiKey
            ctx["via"], ctx["api_key_prefix"] = AuditEvent.Via.API_KEY, prefix
        else:
            ctx["via"] = AuditEvent.Via.WEB
    if actor is not None:
        ctx["actor"] = actor
    if ctx["actor"] is not None:
        ctx["actor_label"] = getattr(ctx["actor"], "email", "") or str(ctx["actor"])
    return ctx


def _plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, models.Model):
        return value.pk
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


def snapshot(obj: models.Model) -> dict:
    """Concrete field values of a model instance, safe for JSON, without secrets."""
    data = {}
    for field in obj._meta.concrete_fields:
        if field.name in SECRET_FIELDS:
            continue
        data[field.name] = _plain(getattr(obj, field.attname))
    return data


def diff(before: dict, after: dict) -> dict:
    """{field: [old, new]} for fields that changed."""
    return {k: [before.get(k), after.get(k)] for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)}


def record(action: str, obj: models.Model | None = None, *, ref: str = "", changes: dict | None = None,
           actor=None, object_type: str = "", object_id: str = "") -> AuditEvent:
    """Write one audit event. Call it inside the same transaction as the change."""
    if obj is not None:
        object_type = object_type or obj._meta.model_name
        object_id = object_id or str(obj.pk)
        ref = ref or str(getattr(obj, "number", "") or getattr(obj, "email", "") or getattr(obj, "name", "") or obj.pk)
    clean = {k: v for k, v in (changes or {}).items() if k not in SECRET_FIELDS}
    return AuditEvent.objects.create(
        action=action, object_type=object_type, object_id=object_id, object_ref=str(ref)[:100],
        changes=_plain_dict(clean), **_actor_context(actor),
    )


def _plain_dict(data: dict) -> dict:
    return {k: (_plain_dict(v) if isinstance(v, dict) else _plain(v)) for k, v in data.items()}


class AuditedModelViewSetMixin:
    """Records create / update (field diff) / delete for a ModelViewSet, in the same transaction as the write."""

    audit_name: str = ""

    def _audit_name(self) -> str:
        return self.audit_name or self.get_queryset().model._meta.model_name

    def perform_create(self, serializer):
        from django.db import transaction

        with transaction.atomic():
            super().perform_create(serializer)
            created = serializer.instance
            record(f"{self._audit_name()}.created", created, changes={"after": snapshot(created)})

    def perform_update(self, serializer):
        from django.db import transaction

        before = snapshot(serializer.instance)
        with transaction.atomic():
            super().perform_update(serializer)
            changes = diff(before, snapshot(serializer.instance))
            if changes:
                record(f"{self._audit_name()}.updated", serializer.instance, changes=changes)

    def perform_destroy(self, instance):
        from django.db import transaction

        before, pk, label = snapshot(instance), instance.pk, str(instance)
        with transaction.atomic():
            super().perform_destroy(instance)
            record(f"{self._audit_name()}.deleted", object_type=instance._meta.model_name, object_id=str(pk),
                   ref=label, changes={"before": before})
