# File: app/casbin_enforcer.py
from fastapi import Depends, HTTPException
from app.core.security import get_current_user
from app.casbin_setup import get_casbin_enforcer

def require_casbin_permission(obj: str, act: str):
    """
    Returns a dependency that ensures the current user's role can do `act` on `obj`.
    e.g. require_casbin_permission("article", "create")
    """
    def checker(current_user=Depends(get_current_user), enforcer=Depends(get_casbin_enforcer)):
        # current_user.role might be "Admin" or "Editor"
        role_name = current_user.role.name if current_user.role else "anonymous"
        allowed = enforcer.enforce(role_name, obj, act)
        if not allowed:
            raise HTTPException(status_code=403, detail=f"Forbidden: no permission for {obj} {act}")
        return current_user
    return checker
