"""
DEPENDENCY INJECTION: decides which class implements each port and builds the use cases.

The use cases only know the ports (`SourceRegistryRepository`, `EventPublisher`); this file plugs in
the real classes. To use another implementation, change it here only. `db` and `uow` come from the
root container (app/container.py).
"""

from dependency_injector import containers, providers
from platform_kit.database import Database, UnitOfWork

from app.modules.source_registry.application.use_cases import SourceRegistryUseCases
from app.modules.source_registry.infrastructure.logging_event_publisher import LoggingEventPublisher
from app.modules.source_registry.infrastructure.persistence.sqlalchemy_source_registry_repository import (
    SqlAlchemySourceRegistryRepository,
)


class SourceRegistryContainer(containers.DeclarativeContainer):
    db = providers.Dependency(instance_of=Database)
    uow = providers.Dependency(instance_of=UnitOfWork)

    # Port -> implementation
    repository = providers.Factory(SqlAlchemySourceRegistryRepository, session=db.provided.scoped_session)
    events = providers.Factory(LoggingEventPublisher, uow=uow)

    # Used by router.py as Provide["source_registry.use_cases"]
    use_cases = providers.Factory(SourceRegistryUseCases, repository=repository, events=events)
