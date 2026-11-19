"""
ADAPTER: the `SourceRegistryRepository` port implemented with SQLAlchemy.

Its only job is translation: entity -> table row when saving, table row -> entity when loading. No
business rules here, and no commit: the request commits when the response is successful.
"""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.source_registry.application.ports import SourceRegistryPage, SourceRegistryRepository
from app.modules.source_registry.domain.entities import SourceRegistry
from app.modules.source_registry.domain.exceptions import SourceRegistryCodeTaken, SourceRegistryNotFound
from app.modules.source_registry.domain.value_objects import (
    SourceRegistryCode,
    SourceRegistryName,
    SourceRegistryStatus,
)
from app.modules.source_registry.infrastructure.persistence.models import SourceRegistryModel


class SqlAlchemySourceRegistryRepository(SourceRegistryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, source_registry: SourceRegistry) -> None:
        row = SourceRegistryModel(
            id=source_registry.id,
            name=source_registry.name.value,
            code=source_registry.code.value,
            status=source_registry.status.value,
            version=1,
        )
        self.session.add(row)
        await self._flush(source_registry.code)
        source_registry.created_at, source_registry.updated_at = row.created_at, row.updated_at

    async def get(self, source_registry_id: UUID) -> SourceRegistry:
        row = await self.session.get(SourceRegistryModel, source_registry_id, populate_existing=True)
        if row is None:
            raise SourceRegistryNotFound()
        return self._to_entity(row)

    async def list(self, *, status: SourceRegistryStatus | None, offset: int, limit: int) -> SourceRegistryPage:
        conditions = [] if status is None else [SourceRegistryModel.status == status.value]
        total = await self.session.scalar(select(func.count()).select_from(SourceRegistryModel).where(*conditions))
        rows = await self.session.scalars(
            select(SourceRegistryModel)
            .where(*conditions)
            .order_by(SourceRegistryModel.name, SourceRegistryModel.id)
            .offset(offset)
            .limit(limit)
        )
        return SourceRegistryPage(items=[self._to_entity(row) for row in rows], total=total or 0)

    async def update(self, source_registry: SourceRegistry) -> None:
        row = await self.session.get(SourceRegistryModel, source_registry.id)
        if row is None:
            raise SourceRegistryNotFound()
        row.name, row.code, row.status = (
            source_registry.name.value,
            source_registry.code.value,
            source_registry.status.value,
        )
        row.version += 1
        await self._flush(source_registry.code)
        source_registry.updated_at = row.updated_at

    async def delete(self, source_registry_id: UUID) -> None:
        result = await self.session.execute(
            delete(SourceRegistryModel).where(SourceRegistryModel.id == source_registry_id)
        )
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise SourceRegistryNotFound()

    async def code_exists(self, code: SourceRegistryCode, *, except_id: UUID | None = None) -> bool:
        query = select(SourceRegistryModel.id).where(SourceRegistryModel.code == code.value)
        if except_id is not None:
            query = query.where(SourceRegistryModel.id != except_id)
        return await self.session.scalar(query.limit(1)) is not None

    async def _flush(self, code: SourceRegistryCode) -> None:
        """Sends the SQL now. If two requests save the same code at once, the unique index wins -> 409."""
        try:
            await self.session.flush()
        except IntegrityError as e:
            raise SourceRegistryCodeTaken(f"Code {code.value} is already used") from e

    @staticmethod
    def _to_entity(row: SourceRegistryModel) -> SourceRegistry:
        """Table row -> entity (value objects are rebuilt, so loaded data is checked too)."""
        return SourceRegistry(
            id=row.id,
            name=SourceRegistryName(row.name),
            code=SourceRegistryCode(row.code),
            status=SourceRegistryStatus(row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
