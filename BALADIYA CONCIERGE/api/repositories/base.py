from __future__ import annotations

import uuid
from typing import Any, Generic, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.infra.db import Base

ModelT = TypeVar("ModelT", bound=Base)


class TenantScopeError(RuntimeError):
    """Raised when a repository is used without a tenant_id."""


class BaseRepository(Generic[ModelT]):
    """Every subclass MUST pass tenant_id at construction time.

    All query methods append .filter(Model.tenant_id == self.tenant_id).
    This is a second isolation layer on top of Postgres RLS — it catches
    queries on tables that might have been added without RLS yet.
    """

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, model: Type[ModelT]) -> None:
        if tenant_id is None:
            raise TenantScopeError(
                f"{self.__class__.__name__} constructed without tenant_id — potential cross-tenant leak"
            )
        self._session = session
        self._tenant_id = tenant_id
        self._model = model

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    def _base_query(self):
        return select(self._model).filter(self._model.tenant_id == self._tenant_id)

    async def get(self, record_id: uuid.UUID) -> ModelT | None:
        stmt = self._base_query().filter(self._model.id == record_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(self, **filters: Any) -> list[ModelT]:
        stmt = self._base_query()
        for attr, value in filters.items():
            stmt = stmt.filter(getattr(self._model, attr) == value)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, instance: ModelT) -> ModelT:
        if getattr(instance, "tenant_id", None) != self._tenant_id:
            raise TenantScopeError(
                f"Attempt to persist {self._model.__name__} with wrong tenant_id"
            )
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self._session.delete(instance)
        await self._session.flush()
