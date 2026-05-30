"""M2 tests — policy/provider models, scoping logic, endpoint auth guards."""
import uuid

import httpx
import pytest

from app.core.security import CurrentUser
from app.main import app
from app.services.policy_service import _accessible_org_filter


def _user(role: str, super_admin: bool = False) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4()),
        org_id=str(uuid.uuid4()), role=role, is_super_admin=super_admin,
    )


def test_models_include_policy_provider():
    from app.db.models import Policy, PolicyDocument, Provider
    assert Policy.__tablename__ == "policies"
    assert Provider.__tablename__ == "providers"
    assert PolicyDocument.__tablename__ == "policy_documents"


def test_accessible_org_filter_scope():
    # Admin/Manager + super admin -> no org restriction (whole group)
    assert _accessible_org_filter(_user("admin")) is None
    assert _accessible_org_filter(_user("manager")) is None
    assert _accessible_org_filter(_user("viewer", super_admin=True)) is None
    # Owner/Viewer -> restricted to their own org
    owner = _user("owner")
    assert _accessible_org_filter(owner) == uuid.UUID(owner.org_id)
    viewer = _user("viewer")
    assert _accessible_org_filter(viewer) == uuid.UUID(viewer.org_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", [
    ("get", "/api/v1/policies"),
    ("post", "/api/v1/policies"),
    ("get", "/api/v1/providers"),
    ("post", "/api/v1/providers"),
])
async def test_m2_endpoints_require_auth(method, path):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        kwargs = {"json": {}} if method == "post" else {}
        resp = await getattr(ac, method)(path, **kwargs)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
