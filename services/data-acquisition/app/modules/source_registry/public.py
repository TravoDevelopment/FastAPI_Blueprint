"""
PUBLIC API of the source_registry module: the ONLY file other modules of this service may import from.

Re-exports only, no logic. Another module that needs source_registry imports `SourceRegistryUseCases`
from here, never from application/ or infrastructure/. Other SERVICES never import this code: they
call `/v1/sources` over HTTP.
"""

from app.modules.source_registry.application.use_cases import (
    RegisterSourceCommand,
    SourceRegistryUseCases,
    UpdateSourceCommand,
)
from app.modules.source_registry.domain.entities import AcquisitionSource

__all__ = [
    "RegisterSourceCommand",
    "UpdateSourceCommand",
    "AcquisitionSource",
    "SourceRegistryUseCases",
]
