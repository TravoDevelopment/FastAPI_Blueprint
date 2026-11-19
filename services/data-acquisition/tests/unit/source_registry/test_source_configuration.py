"""Test SourceConfiguration snapshot invariants and immutability."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.modules.source_registry.domain.entities import SourceConfiguration
from app.modules.source_registry.domain.exceptions import InvalidSourceConfiguration
from app.modules.source_registry.domain.value_objects import (
    ApprovedDomain,
    ApprovedEndpoint,
    ConnectorIdentity,
    EndpointMatch,
    SourceClassification,
)

SOURCE_ID = UUID(int=1)
CREATOR_ID = UUID(int=2)
CREATED_AT = datetime(2026, 1, 1, 12, tzinfo=UTC)
DOMAIN = ApprovedDomain("example.org")
ENDPOINT = ApprovedEndpoint("https://example.org/feed")
CONNECTOR = ConnectorIdentity("example_feed", "2.1.0")


def make_configuration(
    *,
    version: int = 1,
    domains: list[ApprovedDomain] | tuple[ApprovedDomain, ...] = (DOMAIN,),
    endpoints: list[ApprovedEndpoint] | tuple[ApprovedEndpoint, ...] = (ENDPOINT,),
) -> SourceConfiguration:
    """Create a valid snapshot unless a test overrides its version or scope."""
    return SourceConfiguration(
        source_id=SOURCE_ID,
        version=version,
        classification=SourceClassification.OFFICIAL_API,
        approved_domains=domains,
        approved_endpoints=endpoints,
        connector=CONNECTOR,
        created_at=CREATED_AT,
        created_by=CREATOR_ID,
    )


@pytest.mark.parametrize("version", [1, 17])
def test_complete_snapshot_preserves_its_fields(version: int) -> None:
    """Keep the supplied identity, audit fields, and non-default connector."""
    configuration = make_configuration(version=version)

    assert (configuration.source_id, configuration.version) == (SOURCE_ID, version)
    assert configuration.classification is SourceClassification.OFFICIAL_API
    assert configuration.approved_domains == (DOMAIN,)
    assert configuration.approved_endpoints == (ENDPOINT,)
    assert configuration.connector == CONNECTOR
    assert configuration.created_at == CREATED_AT
    assert configuration.created_by == CREATOR_ID


@pytest.mark.parametrize("count", [0, 1, 100, 101])
def test_domain_count_limits(count: int) -> None:
    """Accept one through 100 domains independently of the endpoint count."""
    domains = [ApprovedDomain(f"site-{index}.example.org") for index in range(count)]
    endpoints = [ApprovedEndpoint("https://site-0.example.org/feed")]

    if 1 <= count <= 100:
        assert len(make_configuration(domains=domains, endpoints=endpoints).approved_domains) == count
    else:
        with pytest.raises(InvalidSourceConfiguration, match="approved domains"):
            make_configuration(domains=domains, endpoints=endpoints)


@pytest.mark.parametrize("count", [0, 1, 100, 101])
def test_endpoint_count_limits(count: int) -> None:
    """Accept one through 100 endpoints independently of the domain count."""
    endpoints = [ApprovedEndpoint(f"https://example.org/feed/{index}") for index in range(count)]

    if 1 <= count <= 100:
        assert len(make_configuration(endpoints=endpoints).approved_endpoints) == count
    else:
        with pytest.raises(InvalidSourceConfiguration, match="approved endpoints"):
            make_configuration(endpoints=endpoints)


def test_rejects_duplicate_canonical_domains() -> None:
    """Different spellings of the same canonical hostname count as a duplicate."""
    with pytest.raises(InvalidSourceConfiguration):
        make_configuration(domains=[DOMAIN, ApprovedDomain(" EXAMPLE.ORG. ")])


def test_rejects_duplicate_canonical_endpoint_rules() -> None:
    """An explicit default port and hostname casing do not make a new rule."""
    with pytest.raises(InvalidSourceConfiguration):
        make_configuration(endpoints=[ENDPOINT, ApprovedEndpoint("https://EXAMPLE.ORG:443/feed")])


def test_allows_same_url_with_different_match_modes() -> None:
    """An exact rule and a subtree rule for the same URL are distinct."""
    subtree = ApprovedEndpoint(ENDPOINT.url, EndpointMatch.SUBTREE)

    assert make_configuration(endpoints=[ENDPOINT, subtree]).approved_endpoints == (ENDPOINT, subtree)


@pytest.mark.parametrize("hostname", ["unrelated.example", "api.example.org"])
def test_rejects_endpoint_on_unlisted_host(hostname: str) -> None:
    """Neither unrelated hosts nor subdomains inherit approval from a listed host."""
    with pytest.raises(InvalidSourceConfiguration):
        make_configuration(endpoints=[ENDPOINT, ApprovedEndpoint(f"https://{hostname}/feed", EndpointMatch.SUBTREE)])


def test_accepts_endpoint_on_explicitly_listed_subdomain() -> None:
    """A subdomain is allowed when its own canonical hostname is approved."""
    endpoint = ApprovedEndpoint("https://API.EXAMPLE.ORG/feed")
    configuration = make_configuration(domains=[DOMAIN, ApprovedDomain("api.example.org")], endpoints=[endpoint])

    assert configuration.approved_endpoints == (endpoint,)


@pytest.mark.parametrize("version", [0, -1, True, 1.0, "1"])
def test_rejects_non_positive_or_non_integer_version(version: object) -> None:
    """Reject invalid versions with the existing configuration error and code."""
    with pytest.raises(InvalidSourceConfiguration) as error:
        replace(make_configuration(), version=version)  # type: ignore[arg-type]

    assert error.value.code == "invalid_source_configuration"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("source_id", str(SOURCE_ID)),
        ("created_by", str(CREATOR_ID)),
        ("classification", SourceClassification.OFFICIAL_API.value),
        ("connector", ("example_feed", "2.1.0")),
        ("approved_domains", DOMAIN.value),
        ("approved_domains", [DOMAIN.value]),
        ("approved_endpoints", None),
        ("approved_endpoints", [ENDPOINT.url]),
        ("created_at", CREATED_AT.isoformat()),
        ("created_at", CREATED_AT.replace(tzinfo=None)),
    ],
)
def test_rejects_malformed_snapshot_fields(field_name: str, value: object) -> None:
    """Fail construction when a required field is not a valid domain value."""
    with pytest.raises(InvalidSourceConfiguration):
        replace(make_configuration(), **{field_name: value})  # type: ignore[arg-type]


def test_normalizes_aware_timestamp_to_utc() -> None:
    """Store UTC without changing the instant represented by the input time."""
    offset_time = CREATED_AT.astimezone(timezone(timedelta(hours=5, minutes=30)))
    configuration = replace(make_configuration(), created_at=offset_time)

    assert configuration.created_at == CREATED_AT
    assert configuration.created_at.tzinfo is UTC


def test_snapshot_fields_cannot_be_reassigned() -> None:
    """A frozen configuration rejects normal field reassignment."""
    configuration = make_configuration()

    with pytest.raises(FrozenInstanceError):
        configuration.version = 2  # type: ignore[misc]


def test_snapshot_detaches_from_input_lists_and_preserves_order() -> None:
    """Later mutations of input lists leave the stored tuples and their ordering intact."""
    other_domain = ApprovedDomain("other.example.org")
    other_endpoint = ApprovedEndpoint("https://other.example.org/feed")
    domains = [other_domain, DOMAIN]
    endpoints = [other_endpoint, ENDPOINT]
    configuration = make_configuration(domains=domains, endpoints=endpoints)

    domains.clear()
    endpoints.reverse()

    assert configuration.approved_domains == (other_domain, DOMAIN)
    assert configuration.approved_endpoints == (other_endpoint, ENDPOINT)
