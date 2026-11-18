"""Unit tests for Source Registry eligibility checks and named errors."""

import pytest
from platform_kit.errors import AppError

from app.modules.source_registry.domain.exceptions import (
    DuplicateSourceName,
    SourceConcurrentModification,
    SourceConfigurationNotFound,
    SourceConnectorUnavailable,
    SourceDisabled,
    SourceNotFound,
)
from app.modules.source_registry.domain.policies import (
    ensure_collection_eligible,
    ensure_enable_eligible,
    ensure_replacement_eligible,
)


@pytest.mark.parametrize(
    ("error_type", "code", "status"),
    [
        (DuplicateSourceName, "duplicate_source_name", 409),
        (SourceNotFound, "source_not_found", 404),
        (SourceConfigurationNotFound, "source_configuration_not_found", 404),
        (SourceDisabled, "source_disabled", 409),
        (SourceConnectorUnavailable, "source_connector_unavailable", 409),
        (SourceConcurrentModification, "source_concurrent_modification", 409),
    ],
)
def test_named_error_contract(error_type: type[AppError], code: str, status: int) -> None:
    """Each named registry error has a stable code and the expected platform status."""
    error = error_type("Registry operation failed")
    assert error.code == code
    assert error.status == status


def test_enable_accepts_active_configuration_with_available_connector() -> None:
    """An existing active configuration with an available connector permits enablement."""
    ensure_enable_eligible(active_configuration_exists=True, connector_available=True)


@pytest.mark.parametrize("connector_available", [False, True])
def test_enable_checks_missing_configuration_first(*, connector_available: bool) -> None:
    """Missing active configuration wins even when the connector is also unavailable."""
    with pytest.raises(SourceConfigurationNotFound):
        ensure_enable_eligible(active_configuration_exists=False, connector_available=connector_available)


def test_enable_rejects_unavailable_connector() -> None:
    """Having an active configuration does not make its exact connector version available."""
    with pytest.raises(SourceConnectorUnavailable):
        ensure_enable_eligible(active_configuration_exists=True, connector_available=False)


def test_replacement_accepts_available_connector() -> None:
    """An available connector permits an already validated replacement to become active."""
    ensure_replacement_eligible(connector_available=True)


def test_replacement_rejects_unavailable_connector_regardless_of_source_state() -> None:
    """Replacement activation requires availability without consulting the enabled flag."""
    with pytest.raises(SourceConnectorUnavailable):
        ensure_replacement_eligible(connector_available=False)


def test_collection_accepts_eligible_selected_configuration() -> None:
    """Collection can proceed when the source is enabled and the selected version is usable."""
    ensure_collection_eligible(is_enabled=True, selected_configuration_exists=True, connector_available=True)


@pytest.mark.parametrize("selected_configuration_exists", [False, True])
@pytest.mark.parametrize("connector_available", [False, True])
def test_collection_checks_disabled_source_first(
    *, selected_configuration_exists: bool, connector_available: bool
) -> None:
    """A disabled source wins over either or both configuration and connector failures."""
    with pytest.raises(SourceDisabled):
        ensure_collection_eligible(
            is_enabled=False,
            selected_configuration_exists=selected_configuration_exists,
            connector_available=connector_available,
        )


@pytest.mark.parametrize("connector_available", [False, True])
def test_collection_checks_missing_selected_configuration_next(*, connector_available: bool) -> None:
    """An enabled source with a missing selected version fails before connector availability is considered."""
    with pytest.raises(SourceConfigurationNotFound):
        ensure_collection_eligible(
            is_enabled=True, selected_configuration_exists=False, connector_available=connector_available
        )


def test_collection_rejects_unavailable_selected_connector() -> None:
    """An enabled source with an existing selected version still needs its exact connector."""
    with pytest.raises(SourceConnectorUnavailable):
        ensure_collection_eligible(is_enabled=True, selected_configuration_exists=True, connector_available=False)
