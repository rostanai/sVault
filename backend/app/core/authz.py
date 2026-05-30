"""Authorization — roles, permission matrix, and FastAPI dependencies.

Mirrors docs/PERMISSIONS.md. Two planes: Super Admin (platform) sits above all tenants.
Function-level checks here; object-level (owner == row owner) + RLS happen in services/DB.
"""
from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from fastapi import Depends, Request

from app.core.errors import AppError, ErrorCode
from app.core.security import CurrentUser, decode_token


class Role(StrEnum):
    super_admin = "super_admin"  # platform plane
    admin = "admin"
    manager = "manager"
    owner = "owner"
    viewer = "viewer"


# resource:action -> roles allowed (function level). Super admin bypasses everything.
# "owner" here means the role may act, subject to object-level ownership in the service layer.
_MATRIX: dict[str, set[Role]] = {
    "policy:create": {Role.admin, Role.manager, Role.owner},
    "policy:read": {Role.admin, Role.manager, Role.owner, Role.viewer},
    "policy:update": {Role.admin, Role.manager, Role.owner},
    "policy:delete": {Role.admin, Role.manager},
    "document:write": {Role.admin, Role.manager, Role.owner},
    "document:delete": {Role.admin, Role.manager},
    "alert:configure": {Role.admin, Role.manager, Role.owner},
    "approval:submit": {Role.admin, Role.manager, Role.owner},
    "approval:approve": {Role.admin, Role.manager},
    "approve:self": {Role.admin, Role.manager},
    "provider:manage": {Role.admin, Role.manager},
    "user:manage": {Role.admin},
    "org:manage": {Role.admin},
    "billing:manage": {Role.admin},
    "apikey:manage": {Role.admin},
    "audit:view": {Role.admin},
}


def has_permission(user: CurrentUser, permission: str) -> bool:
    if user.is_super_admin:
        return True
    allowed = _MATRIX.get(permission)
    if allowed is None:
        return False
    try:
        return Role(user.role) in allowed
    except ValueError:
        return False


# ---- FastAPI dependencies ----
def get_current_user(request: Request) -> CurrentUser:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AppError(ErrorCode.unauthorized, "Missing bearer token")
    return decode_token(auth.removeprefix("Bearer ").strip())


def require_permission(permission: str) -> Callable[..., CurrentUser]:
    """Dependency factory: 403 if the user's role lacks `permission`."""

    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not has_permission(user, permission):
            raise AppError(
                ErrorCode.forbidden, f"Your role can't perform {permission}"
            )
        return user

    return _dep


def require_super_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_super_admin:
        # 404 (not 403) keeps platform routes invisible to tenant users.
        raise AppError(ErrorCode.not_found, "Not found")
    return user
