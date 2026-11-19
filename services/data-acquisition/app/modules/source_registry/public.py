"""
PUBLIC API of the source_registry module: the ONLY file other modules of this service may import from.

Re-exports only, no logic. Another module that needs source registry imports `SourceRegistryUseCases`
from here, never from application/ or infrastructure/. Other SERVICES never import this code: they
call `/v1/source-registry` over HTTP.
"""

from app.modules.source_registry.application.use_cases import (
    CreateSourceRegistryCommand,
    SourceRegistryUseCases,
    UpdateSourceRegistryCommand,
)
from app.modules.source_registry.domain.entities import SourceRegistry
from app.modules.source_registry.domain.value_objects import SourceRegistryStatus

__all__ = [
    "CreateSourceRegistryCommand",
    "UpdateSourceRegistryCommand",
    "SourceRegistry",
    "SourceRegistryStatus",
    "SourceRegistryUseCases",
]
