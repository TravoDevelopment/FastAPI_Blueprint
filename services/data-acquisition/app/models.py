"""Model registry for Alembic and tests: import every module's ORM models here."""

from app.db import Base
from app.modules.source_registry.infrastructure.persistence.models import SourceRegistryModel  # noqa: F401

__all__ = ["Base"]
