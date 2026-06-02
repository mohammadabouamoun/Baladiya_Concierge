"""CMS route dependencies — requires tenant_admin role."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.core.security import TokenClaims, get_current_user


async def require_tenant_admin(
    token: Annotated[TokenClaims, Depends(get_current_user)],
) -> TokenClaims:
    if token.role != "tenant_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant Admin access required",
        )
    return token
