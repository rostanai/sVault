"""M1 unit tests — claim extraction + permission matrix (no DB needed)."""
import pytest
from jose import jwt

from app.core.authz import Role, has_permission, require_super_admin
from app.core.errors import AppError
from app.core.security import CurrentUser, decode_token, extract_claims


def _user(role: str = "", super_admin: bool = False) -> CurrentUser:
    return CurrentUser(user_id="u1", tenant_id="t1", org_id="o1", role=role,
                       is_super_admin=super_admin)


def test_extract_claims_reads_app_metadata():
    payload = {
        "sub": "user-123", "email": "a@b.com",
        "app_metadata": {"tenant_id": "t1", "org_id": "o1", "role": "admin",
                         "is_platform_admin": False},
        "user_metadata": {"role": "super_admin"},  # must be IGNORED (user-editable)
    }
    u = extract_claims(payload)
    assert u.user_id == "user-123"
    assert u.tenant_id == "t1" and u.org_id == "o1" and u.role == "admin"
    assert u.is_super_admin is False


def test_super_admin_bypasses_all():
    u = _user(super_admin=True)
    assert has_permission(u, "policy:delete")
    assert has_permission(u, "user:manage")
    assert has_permission(u, "anything:unknown")  # super admin -> always true


@pytest.mark.parametrize(
    "role,perm,expected",
    [
        ("admin", "policy:delete", True),
        ("manager", "policy:delete", True),
        ("owner", "policy:delete", False),
        ("owner", "policy:create", True),
        ("viewer", "policy:read", True),
        ("viewer", "policy:create", False),
        ("owner", "approval:approve", False),
        ("admin", "user:manage", True),
        ("manager", "user:manage", False),
        ("admin", "unknown:action", False),  # not super admin + unknown -> deny
    ],
)
def test_permission_matrix(role, perm, expected):
    assert has_permission(_user(role=role), perm) is expected


def test_require_super_admin_hides_route_as_404():
    with pytest.raises(AppError) as exc:
        require_super_admin(_user(role="admin"))
    assert exc.value.code.value == "not_found"  # 404, not 403 — no existence leak


def test_decode_token_roundtrip(monkeypatch):
    from app.core import config, security
    monkeypatch.setattr(config.settings, "supabase_jwt_secret", "test-secret")
    monkeypatch.setattr(security.settings, "supabase_jwt_secret", "test-secret")
    token = jwt.encode(
        {"sub": "u9", "app_metadata": {"tenant_id": "t9", "role": "manager"}},
        "test-secret", algorithm="HS256",
    )
    u = decode_token(token)
    assert u.user_id == "u9" and u.tenant_id == "t9" and u.role == "manager"


def test_decode_token_rejects_bad_signature(monkeypatch):
    from app.core import config, security
    monkeypatch.setattr(config.settings, "supabase_jwt_secret", "real-secret")
    monkeypatch.setattr(security.settings, "supabase_jwt_secret", "real-secret")
    forged = jwt.encode({"sub": "x"}, "wrong-secret", algorithm="HS256")
    with pytest.raises(AppError) as exc:
        decode_token(forged)
    assert exc.value.code.value == "unauthorized"


def test_roles_enum_complete():
    assert {r.value for r in Role} == {
        "super_admin", "admin", "manager", "owner", "viewer"
    }
