from accounts.apikeys import ApiKey
from rest_framework.test import APIClient

from .conftest import client_for


def test_api_key_lifecycle_scopes_and_idempotency(admin_user, golden):
    admin = client_for(admin_user)
    r = admin.post("/api/api-keys", {"name": "ERP", "scopes": ["read"]}, format="json")
    assert r.status_code == 201
    raw, key_id = r.json()["key"], r.json()["id"]
    assert raw.startswith("bl_") and raw not in str(ApiKey.objects.values_list("key_hash", flat=True))

    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw)
    assert c.get("/api/v1/subscriptions").status_code == 200
    body = {"name": "From ERP", "email": "erp@example.com"}
    assert c.post("/api/v1/customers", body, format="json").status_code == 403  # read-only key

    w = admin.post("/api/api-keys", {"name": "ERP write", "scopes": ["read", "write"]}, format="json").json()["key"]
    c.credentials(HTTP_X_API_KEY=w, HTTP_IDEMPOTENCY_KEY="create-erp-1")
    first = c.post("/api/v1/customers", body, format="json")
    again = c.post("/api/v1/customers", body, format="json")
    assert first.status_code == again.status_code == 201
    assert first.json()["id"] == again.json()["id"] and again["Idempotent-Replayed"] == "true"

    assert admin.post(f"/api/api-keys/{key_id}/revoke").json()["revoked_at"]
    c.credentials(HTTP_X_API_KEY=raw)
    assert c.get("/api/v1/subscriptions").status_code == 401
    c.credentials(HTTP_X_API_KEY="bl_nope_nope")
    assert c.get("/api/v1/subscriptions").status_code == 401


def test_only_admin_manages_keys(staff_user):
    assert client_for(staff_user).post("/api/api-keys", {"name": "x", "scopes": ["read"]}, format="json").status_code == 403
