from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from api.core.security import TokenClaims, get_current_user


async def require_platform_manager(
    token: Annotated[TokenClaims, Depends(get_current_user)],
) -> TokenClaims:
    """Validate that the caller is a Platform Manager.

    Platform Manager routes deliberately never set the RLS session variable.
    Any query against a tenant-owned table from this context will be rejected
    by RLS — that is the intended behaviour.
    """
    if token.role != "platform_manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Manager access required",
        )
    return token
