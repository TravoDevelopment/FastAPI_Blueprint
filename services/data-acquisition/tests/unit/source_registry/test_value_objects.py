"""
Value-object tests for the Source Registry.

They run without a database or HTTP layer: each object either normalizes the input or raises the
domain error that represents the broken rule.
"""

import pytest

from app.modules.source_registry.domain.exceptions import (
    InvalidApprovedDomain,
    InvalidApprovedEndpoint,
    InvalidConnectorIdentity,
    InvalidSourceClassification,
    InvalidSourceDescription,
    InvalidSourceName,
)
from app.modules.source_registry.domain.value_objects import (
    SOURCE_DESCRIPTION_MAX_LENGTH,
    SOURCE_NAME_MAX_LENGTH,
    ApprovedDomain,
    ApprovedEndpoint,
    ConnectorIdentity,
    EndpointMatch,
    SourceClassification,
    SourceDescription,
    SourceName,
)

# --- SourceName ------------------------------------------------------------------------------------


def test_source_name_normalizes_whitespace() -> None:
    assert SourceName("  Blue   pen ").value == "Blue pen"


def test_source_name_keeps_case() -> None:
    assert SourceName("Blue Pen").value == "Blue Pen"


@pytest.mark.parametrize("raw", ["", "ab", "   ", "x" * (SOURCE_NAME_MAX_LENGTH + 1)])
def test_source_name_must_be_3_to_120_characters(raw: str) -> None:
    with pytest.raises(InvalidSourceName):
        SourceName(raw)


def test_source_name_rejects_non_text() -> None:
    with pytest.raises(InvalidSourceName):
        SourceName(123)  # type: ignore[arg-type]


# --- SourceDescription -----------------------------------------------------------------------------


def test_source_description_none_stays_none() -> None:
    assert SourceDescription(None).value is None


def test_source_description_is_trimmed() -> None:
    assert SourceDescription("  Official source page  ").value == "Official source page"


@pytest.mark.parametrize("raw", ["", "   ", "\n\t"])
def test_blank_source_description_becomes_none(raw: str) -> None:
    assert SourceDescription(raw).value is None


def test_source_description_accepts_the_maximum_length() -> None:
    assert SourceDescription("x" * SOURCE_DESCRIPTION_MAX_LENGTH).value == "x" * SOURCE_DESCRIPTION_MAX_LENGTH


def test_source_description_rejects_more_than_the_maximum_length() -> None:
    with pytest.raises(InvalidSourceDescription):
        SourceDescription("x" * (SOURCE_DESCRIPTION_MAX_LENGTH + 1))


def test_source_description_rejects_non_text() -> None:
    with pytest.raises(InvalidSourceDescription):
        SourceDescription(123)  # type: ignore[arg-type]


# --- SourceClassification --------------------------------------------------------------------------


def test_source_classification_values() -> None:
    assert SourceClassification.parse("official_website") is SourceClassification.OFFICIAL_WEBSITE
    assert SourceClassification.parse("third_party_website") is SourceClassification.THIRD_PARTY_WEBSITE
    assert SourceClassification.parse("official_api") is SourceClassification.OFFICIAL_API
    assert SourceClassification.parse("third_party_api") is SourceClassification.THIRD_PARTY_API
    assert SourceClassification.parse("other_approved_source") is SourceClassification.OTHER_APPROVED_SOURCE


def test_source_classification_rejects_unknown_values() -> None:
    with pytest.raises(InvalidSourceClassification):
        SourceClassification.parse("official_blog")


# --- ApprovedDomain --------------------------------------------------------------------------------


def test_approved_domain_is_lower_case_and_has_no_trailing_dot() -> None:
    assert ApprovedDomain(" Example.COM. ").value == "example.com"


def test_approved_domain_converts_internationalized_names() -> None:
    assert ApprovedDomain("bücher.example").value == "xn--bcher-kva.example"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "localhost",
        "example",
        "example..com",
        "example.com:443",
        "https://example.com",
        "example.com/path",
        "*.example.com",
        "-example.com",
        "example-.com",
        "exa_mple.com",
        "127.0.0.1",
        "::1",
        "foo.local",
        "foo.localhost",
        "foo.internal",
        "foo.lan",
        "home.arpa",
        "foo.home.arpa",
        "a" * 64 + ".com",
        ".".join(["a" * 63] * 4),
    ],
)
def test_approved_domain_rejects_invalid_hostnames(raw: str) -> None:
    with pytest.raises(InvalidApprovedDomain):
        ApprovedDomain(raw)


def test_approved_domain_rejects_non_text() -> None:
    with pytest.raises(InvalidApprovedDomain):
        ApprovedDomain(123)  # type: ignore[arg-type]


# --- ApprovedEndpoint ------------------------------------------------------------------------------


def test_approved_endpoint_normalizes_host_and_defaults_to_exact() -> None:
    endpoint = ApprovedEndpoint("https://Example.COM./api")
    assert endpoint.url == "https://example.com/api"
    assert endpoint.match is EndpointMatch.EXACT


def test_approved_endpoint_normalizes_a_missing_path_to_root() -> None:
    assert ApprovedEndpoint("https://example.com").url == "https://example.com/"


def test_approved_endpoint_accepts_an_explicit_443_port() -> None:
    assert ApprovedEndpoint("https://example.com:443/api").url == "https://example.com/api"


def test_approved_endpoint_accepts_exact_and_subtree_matches() -> None:
    assert ApprovedEndpoint("https://example.com/api", EndpointMatch.EXACT).match is EndpointMatch.EXACT
    assert ApprovedEndpoint("https://example.com/api/", EndpointMatch.SUBTREE).match is EndpointMatch.SUBTREE


@pytest.mark.parametrize(
    "raw",
    [
        "http://example.com/api",
        "https://example.com:8443/api",
        "https://example.com:0/api",
        "https://user:password@example.com/api",
        "https://example.com/api?page=1",
        "https://example.com/api#section",
        "https://example.com/api/*",
        "https://example.com/api\\path",
        "https://127.0.0.1/api",
        "https://localhost/api",
        "https://*.example.com/api",
        "https:///api",
    ],
)
def test_approved_endpoint_rejects_invalid_rules(raw: str) -> None:
    with pytest.raises(InvalidApprovedEndpoint):
        ApprovedEndpoint(raw)


def test_approved_endpoint_rejects_an_invalid_port() -> None:
    with pytest.raises(InvalidApprovedEndpoint):
        ApprovedEndpoint("https://example.com:not-a-port/api")


def test_approved_endpoint_rejects_an_unknown_match() -> None:
    with pytest.raises(InvalidApprovedEndpoint):
        ApprovedEndpoint("https://example.com/api", "prefix")  # type: ignore[arg-type]


def test_approved_endpoint_rejects_non_text() -> None:
    with pytest.raises(InvalidApprovedEndpoint):
        ApprovedEndpoint(123)  # type: ignore[arg-type]


# --- ConnectorIdentity -----------------------------------------------------------------------------


def test_connector_identity_accepts_the_default_connector() -> None:
    connector = ConnectorIdentity(" web_scraper ", "1.0.0")
    assert (connector.key, connector.version) == ("web_scraper", "1.0.0")


def test_connector_identity_normalizes_the_key_to_lower_case() -> None:
    assert ConnectorIdentity("Web_Scraper", "1.0.0").key == "web_scraper"


def test_connector_identity_accepts_semantic_version_suffixes() -> None:
    assert ConnectorIdentity("web_scraper", "1.0.0-beta.1").version == "1.0.0-beta.1"
    assert ConnectorIdentity("web_scraper", "1.0.0+build.5").version == "1.0.0+build.5"


@pytest.mark.parametrize("key", ["", "web scraper", "web/scraper", "-web", "w" * 65])
def test_connector_identity_rejects_invalid_keys(key: str) -> None:
    with pytest.raises(InvalidConnectorIdentity):
        ConnectorIdentity(key, "1.0.0")


@pytest.mark.parametrize("version", ["", "1.0", "v1.0.0", "1.0.0.0"])
def test_connector_identity_rejects_invalid_versions(version: str) -> None:
    with pytest.raises(InvalidConnectorIdentity):
        ConnectorIdentity("web_scraper", version)


def test_connector_identity_rejects_non_text() -> None:
    with pytest.raises(InvalidConnectorIdentity):
        ConnectorIdentity(123, "1.0.0")  # type: ignore[arg-type]


def test_connector_identity_is_compared_by_value() -> None:
    assert ConnectorIdentity("web_scraper", "1.0.0") == ConnectorIdentity("Web_Scraper", " 1.0.0 ")
