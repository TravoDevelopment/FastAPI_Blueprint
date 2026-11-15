"""Model registry for Alembic and tests: import every module's ORM models here."""

from app.db import Base

__all__ = ["Base"]
