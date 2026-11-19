"""
VALUE OBJECTS: small values that check and clean themselves when they are created.

If the input is wrong they raise, so an invalid source name, domain, endpoint or connector can never
exist anywhere in the code and no other layer has to check it again. They cannot be changed after
creation (`frozen=True`).

The six Source Registry value objects are:

    SourceName           whitespace-normalized, 3-120 characters
    SourceDescription    trimmed, blank becomes None, max 2,000 characters
    SourceClassification one of the five approved classifications
    ApprovedDomain       canonical public DNS hostname
    ApprovedEndpoint     HTTPS, port 443, GET-only endpoint rule (exact or subtree)
    ConnectorIdentity    exact connector key and version

Rules that involve several values (duplicate domains, 1-100 items, endpoint host must belong to an
approved domain) belong to `SourceConfiguration` in a later step.

The generated `SourceRegistryName`, `SourceRegistryCode` and `SourceRegistryStatus` example classes
are kept here temporarily until the generated entity is replaced.
"""

import ipaddress
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from app.modules.source_registry.domain.exceptions import (
    InvalidApprovedDomain,
    InvalidApprovedEndpoint,
    InvalidConnectorIdentity,
    InvalidSourceClassification,
    InvalidSourceDescription,
    InvalidSourceName,
    InvalidSourceRegistryCode,
    InvalidSourceRegistryName,
)

SOURCE_NAME_MIN_LENGTH = 3
SOURCE_NAME_MAX_LENGTH = 120
SOURCE_DESCRIPTION_MAX_LENGTH = 2_000
APPROVED_DOMAIN_MAX_LENGTH = 253
APPROVED_DOMAIN_LABEL_MAX_LENGTH = 63
LOCAL_ONLY_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa")
CONNECTOR_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
CONNECTOR_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
_DOMAIN_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_FORBIDDEN_HOST_CHARACTERS = "/*:@?#[]"


@dataclass(frozen=True, slots=True)
class SourceName:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidSourceName("Source name must be text")
        cleaned = " ".join(self.value.split())
        if not SOURCE_NAME_MIN_LENGTH <= len(cleaned) <= SOURCE_NAME_MAX_LENGTH:
            raise InvalidSourceName(
                f"Source name must contain {SOURCE_NAME_MIN_LENGTH}-{SOURCE_NAME_MAX_LENGTH} characters"
            )
        object.__setattr__(self, "value", cleaned)


@dataclass(frozen=True, slots=True)
class SourceDescription:
    value: str | None

    def __post_init__(self) -> None:
        if self.value is None:
            return
        if not isinstance(self.value, str):
            raise InvalidSourceDescription("Source description must be text or null")
        cleaned = self.value.strip()
        if len(cleaned) > SOURCE_DESCRIPTION_MAX_LENGTH:
            raise InvalidSourceDescription(
                f"Source description must be at most {SOURCE_DESCRIPTION_MAX_LENGTH} characters"
            )
        object.__setattr__(self, "value", cleaned or None)


class SourceClassification(StrEnum):
    OFFICIAL_WEBSITE = "official_website"
    THIRD_PARTY_WEBSITE = "third_party_website"
    OFFICIAL_API = "official_api"
    THIRD_PARTY_API = "third_party_api"
    OTHER_APPROVED_SOURCE = "other_approved_source"

    @classmethod
    def parse(cls, value: str) -> "SourceClassification":
        try:
            return cls(value)
        except ValueError as e:
            raise InvalidSourceClassification(f"Unknown source classification: {value!r}") from e


def _normalize_domain(raw: str) -> str:
    if not isinstance(raw, str):
        raise InvalidApprovedDomain("Domain must be text")
    cleaned = raw.strip().lower().rstrip(".")
    if not cleaned:
        raise InvalidApprovedDomain("Domain must not be empty")
    if any(character in cleaned for character in _FORBIDDEN_HOST_CHARACTERS):
        raise InvalidApprovedDomain("Domain must not contain a scheme, port, path, wildcard or brackets")
    if cleaned == "localhost" or any(
        cleaned == suffix.lstrip(".") or cleaned.endswith(suffix) for suffix in LOCAL_ONLY_SUFFIXES
    ):
        raise InvalidApprovedDomain("Local-only hostnames are not allowed")
    try:
        ipaddress.ip_address(cleaned)
    except ValueError:
        pass
    else:
        raise InvalidApprovedDomain("IP addresses are not allowed")
    try:
        ascii_domain = cleaned.encode("idna").decode("ascii").rstrip(".").lower()
    except UnicodeError as e:
        raise InvalidApprovedDomain("Domain is not a valid internationalized hostname") from e
    if len(ascii_domain) > APPROVED_DOMAIN_MAX_LENGTH:
        raise InvalidApprovedDomain(f"Domain must be at most {APPROVED_DOMAIN_MAX_LENGTH} characters")
    labels = ascii_domain.split(".")
    if len(labels) < 2:
        raise InvalidApprovedDomain("Domain must contain at least two labels")
    for label in labels:
        if len(label) > APPROVED_DOMAIN_LABEL_MAX_LENGTH or not _DOMAIN_LABEL_PATTERN.fullmatch(label):
            raise InvalidApprovedDomain(f"Invalid domain label: {label!r}")
    return ascii_domain


@dataclass(frozen=True, slots=True)
class ApprovedDomain:
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _normalize_domain(self.value))


class EndpointMatch(StrEnum):
    EXACT = "exact"
    SUBTREE = "subtree"


@dataclass(frozen=True, slots=True)
class ApprovedEndpoint:
    url: str
    match: EndpointMatch = EndpointMatch.EXACT

    def __post_init__(self) -> None:
        if not isinstance(self.url, str):
            raise InvalidApprovedEndpoint("Endpoint URL must be text")
        if not isinstance(self.match, EndpointMatch):
            try:
                match = EndpointMatch(self.match)
            except ValueError as e:
                raise InvalidApprovedEndpoint("Endpoint match must be 'exact' or 'subtree'") from e
        else:
            match = self.match
        parsed = urlsplit(self.url.strip())
        if parsed.scheme.lower() != "https":
            raise InvalidApprovedEndpoint("Endpoint URL must use HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise InvalidApprovedEndpoint("Endpoint URL must not contain credentials")
        if parsed.query or parsed.fragment:
            raise InvalidApprovedEndpoint("Endpoint URL must not contain a query string or fragment")
        hostname = parsed.hostname
        if hostname is None:
            raise InvalidApprovedEndpoint("Endpoint URL must contain a hostname")
        try:
            port = parsed.port
        except ValueError as e:
            raise InvalidApprovedEndpoint("Endpoint URL contains an invalid port") from e
        if port not in (None, 443):
            raise InvalidApprovedEndpoint("Endpoint URL must use port 443")
        try:
            host = _normalize_domain(hostname)
        except InvalidApprovedDomain as e:
            raise InvalidApprovedEndpoint(str(e)) from e
        path = parsed.path or "/"
        if not path.startswith("/"):
            raise InvalidApprovedEndpoint("Endpoint path must start with '/'")
        if "*" in path or "\\" in path:
            raise InvalidApprovedEndpoint("Endpoint path must not contain wildcards or backslashes")
        object.__setattr__(self, "url", f"https://{host}{path}")
        object.__setattr__(self, "match", match)


@dataclass(frozen=True, slots=True)
class ConnectorIdentity:
    key: str
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not isinstance(self.version, str):
            raise InvalidConnectorIdentity("Connector key and version must be text")
        key = self.key.strip().lower()
        version = self.version.strip()
        if not CONNECTOR_KEY_PATTERN.fullmatch(key):
            raise InvalidConnectorIdentity(
                "Connector key must be 1-64 lowercase letters, digits, dots, underscores or dashes"
            )
        if not CONNECTOR_VERSION_PATTERN.fullmatch(version):
            raise InvalidConnectorIdentity("Connector version must be a semantic version such as 1.0.0")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "version", version)


# --- Generated example value objects (temporary, removed when the example entity is replaced) ---------


NAME_MIN_LENGTH = 3
NAME_MAX_LENGTH = 120
CODE_MAX_LENGTH = 20
CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,19}$")


class SourceRegistryStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class SourceRegistryName:
    value: str

    def __post_init__(self) -> None:
        cleaned = " ".join(self.value.split())
        if not NAME_MIN_LENGTH <= len(cleaned) <= NAME_MAX_LENGTH:
            raise InvalidSourceRegistryName(f"Name must contain {NAME_MIN_LENGTH}-{NAME_MAX_LENGTH} characters")
        object.__setattr__(self, "value", cleaned)


@dataclass(frozen=True, slots=True)
class SourceRegistryCode:
    value: str

    def __post_init__(self) -> None:
        cleaned = self.value.strip().upper()
        if not CODE_PATTERN.match(cleaned):
            raise InvalidSourceRegistryCode("Code must be 2-20 letters, digits or dashes, e.g. ITM-001")
        object.__setattr__(self, "value", cleaned)
