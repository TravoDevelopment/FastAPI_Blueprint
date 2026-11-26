"""
ADAPTER: the `SourceRegistryRepository` port implemented with SQLAlchemy.

Its only job is translation: entity -> table row when saving, table row -> entity when loading. No
business rules here, and no commit: the request commits when the response is successful.

SourceInUse is raised when a scraping job FK RESTRICT prevents deletion (IntegrityError from DB).
"""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.source_registry.application.ports import SourcePage, SourceRegistryRepository
from app.modules.source_registry.domain.entities import AcquisitionSource
from app.modules.source_registry.domain.exceptions import SourceInUse, SourceNameTaken, SourceNotFound
from app.modules.source_registry.domain.value_objects import (
    SourceDescription,
    SourceName,
    SourceUrlList,
)
from app.modules.source_registry.infrastructure.persistence.models import AcquisitionSourceModel


class SqlAlchemySourceRegistryRepository(SourceRegistryRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, source: AcquisitionSource) -> None:
        row = AcquisitionSourceModel(
            id=source.id,
            name=source.name.value,
            name_key=source.name.key,
            description=source.description.value,
            is_enabled=source.is_enabled,
            source_urls=[u.value for u in source.source_urls.urls],
            created_by=source.created_by,
            updated_by=source.updated_by,
            version=1,
        )
        self.session.add(row)
        await self._flush_name(source.name)
        source.created_at, source.updated_at = row.created_at, row.updated_at

    async def get(self, source_id: UUID) -> AcquisitionSource:
        row = await self.session.get(AcquisitionSourceModel, source_id, populate_existing=True)
        if row is None:
            raise SourceNotFound()
        return self._to_entity(row)

    async def list(
        self,
        *,
        is_enabled: bool | None,
        name_contains: str | None,
        offset: int,
        limit: int,
    ) -> SourcePage:
        conditions = []
        if is_enabled is not None:
            conditions.append(AcquisitionSourceModel.is_enabled == is_enabled)
        if name_contains is not None:
            conditions.append(AcquisitionSourceModel.name_key.contains(name_contains.casefold(), autoescape=True))

        total = await self.session.scalar(select(func.count()).select_from(AcquisitionSourceModel).where(*conditions))
        rows = await self.session.scalars(
            select(AcquisitionSourceModel)
            .where(*conditions)
            .order_by(AcquisitionSourceModel.name_key, AcquisitionSourceModel.id)
            .offset(offset)
            .limit(limit)
        )
        return SourcePage(sources=[self._to_entity(r) for r in rows], total=total or 0)

    async def update(self, source: AcquisitionSource) -> None:
        row = await self.session.get(AcquisitionSourceModel, source.id)
        if row is None:
            raise SourceNotFound()
        row.name = source.name.value
        row.name_key = source.name.key
        row.description = source.description.value
        row.is_enabled = source.is_enabled
        row.source_urls = [u.value for u in source.source_urls.urls]
        row.updated_by = source.updated_by
        row.version += 1
        await self._flush_name(source.name)
        await self.session.refresh(row, ["updated_at"])
        source.updated_at = row.updated_at

    async def delete(self, source_id: UUID) -> None:
        try:
            result = await self.session.execute(
                delete(AcquisitionSourceModel).where(AcquisitionSourceModel.id == source_id)
            )
        except IntegrityError as e:
            raise SourceInUse("Cannot delete source: one or more scraping jobs still reference it") from e
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise SourceNotFound()

    async def name_exists(self, name: SourceName, *, except_id: UUID | None = None) -> bool:
        query = select(AcquisitionSourceModel.id).where(AcquisitionSourceModel.name_key == name.key)
        if except_id is not None:
            query = query.where(AcquisitionSourceModel.id != except_id)
        return await self.session.scalar(query.limit(1)) is not None

    async def _flush_name(self, name: SourceName) -> None:
        """Sends the SQL now. If two requests save the same name_key at once, the unique index wins -> 409."""
        try:
            await self.session.flush()
        except IntegrityError as e:
            raise SourceNameTaken(f"A source named {name.value!r} already exists") from e

    @staticmethod
    def _to_entity(row: AcquisitionSourceModel) -> AcquisitionSource:
        """Table row -> entity (value objects are rebuilt, so loaded data is checked too)."""
        return AcquisitionSource(
            id=row.id,
            name=SourceName(row.name),
            description=SourceDescription(row.description),
            is_enabled=row.is_enabled,
            source_urls=SourceUrlList(row.source_urls),
            created_by=row.created_by,
            updated_by=row.updated_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
