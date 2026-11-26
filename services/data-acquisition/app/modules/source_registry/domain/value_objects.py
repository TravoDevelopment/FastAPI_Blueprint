"""
VALUE OBJECTS: small values that check and clean themselves when they are created.

If the input is wrong they raise, so an invalid name, description or URL can never exist anywhere
in the code and no other layer has to check it again. They cannot be changed after creation
(`frozen=True`).

    SourceName("  Tourism Website A  ").value     ->  "Tourism Website A"  (whitespace collapsed, NFC)
    SourceName("ab")                              ->  raises InvalidSourceName
    SourceDescription("").value                   ->  None                 (blank becomes None)
    SourceUrl("https://example.com/page").value   ->  "https://example.com/page"
    SourceUrl("http://example.com/page")          ->  raises InvalidSourceUrl  (must be HTTPS)
    SourceUrlList(["https://example.com/p"]).urls ->  [SourceUrl(...)]     (deduplicated, validated)
    SourceUrlList([])                             ->  raises EmptySourceUrls
"""

import ipaddress
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urlparse

from app.modules.source_registry.domain.exceptions import (
    EmptySourceUrls,
    InvalidSourceDescription,
    InvalidSourceName,
    InvalidSourceUrl,
    UrlCountExceeded,
)

NAME_MIN_LENGTH = 3
NAME_MAX_LENGTH = 120
DESCRIPTION_MAX_LENGTH = 2_000
URL_MAX_BYTES = 2_048
URL_MAX_COUNT = 100

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
]
_WILDCARD_RE = re.compile(r"\*")


@dataclass(frozen=True, slots=True)
class SourceName:
    value: str

    def __post_init__(self) -> None:
        cleaned = " ".join(unicodedata.normalize("NFC", self.value).split())  # 1. clean
        if not NAME_MIN_LENGTH <= len(cleaned) <= NAME_MAX_LENGTH:  # 2. check
            raise InvalidSourceName(
                f"Source name must be {NAME_MIN_LENGTH}–{NAME_MAX_LENGTH} characters "
                f"after normalisation; got {len(cleaned)}"
            )
        object.__setattr__(self, "value", cleaned)  # 3. keep

    @property
    def key(self) -> str:
        """Casefolded key used for the database UNIQUE constraint."""
        return self.value.casefold()


@dataclass(frozen=True, slots=True)
class SourceDescription:
    value: str | None

    def __post_init__(self) -> None:
        if self.value is None:
            return
        trimmed = self.value.strip()
        if not trimmed:  # blank -> None
            object.__setattr__(self, "value", None)
            return
        if len(trimmed) > DESCRIPTION_MAX_LENGTH:  # check length
            raise InvalidSourceDescription(
                f"Description must not exceed {DESCRIPTION_MAX_LENGTH} characters; got {len(trimmed)}"
            )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True, slots=True)
class SourceUrl:
    value: str

    def __post_init__(self) -> None:
        raw = self.value.strip()
        try:
            parsed = urlparse(raw)
            hostname = parsed.hostname
            _ = parsed.port  # Accessing the port validates its syntax and range.
        except ValueError as exc:
            raise InvalidSourceUrl("URL has an invalid host or port") from exc
        if parsed.scheme != "https":  # 1. must be HTTPS
            raise InvalidSourceUrl(f"URL must use HTTPS: {raw!r}")
        if not hostname:  # 2. must have a host
            raise InvalidSourceUrl(f"URL has no valid host: {raw!r}")
        if _WILDCARD_RE.search(raw):  # 3. no wildcards
            raise InvalidSourceUrl(f"Wildcard patterns are not allowed: {raw!r}")
        try:  # 4. no private IPs
            addr = ipaddress.ip_address(hostname)
            if any(addr in net for net in _PRIVATE_NETWORKS):
                raise InvalidSourceUrl(f"URL resolves to a private or reserved IP: {raw!r}")
        except ValueError:
            pass  # hostname, not an IP literal
        if len(raw.encode()) > URL_MAX_BYTES:  # 5. byte length limit
            raise InvalidSourceUrl(f"URL exceeds {URL_MAX_BYTES} bytes: {raw!r}")
        object.__setattr__(self, "value", raw)


@dataclass(frozen=True, slots=True)
class SourceUrlList:
    """
    A validated, deduplicated list of SourceUrl values for one source.
    """

    urls: tuple[SourceUrl, ...]

    def __init__(self, raw_urls: list[str]) -> None:
        if not raw_urls:
            raise EmptySourceUrls("source_urls must contain at least one URL")
        if len(raw_urls) > URL_MAX_COUNT:
            raise UrlCountExceeded(f"source_urls must not exceed {URL_MAX_COUNT} URLs; got {len(raw_urls)}")
        seen: dict[str, SourceUrl] = {}
        for raw in raw_urls:
            vo = SourceUrl(raw)  # validates each URL; raises InvalidSourceUrl on bad input
            seen[vo.value] = vo  # deduplicate by canonical value
        object.__setattr__(self, "urls", tuple(seen.values()))

    def __iter__(self) -> Iterator[SourceUrl]:
        return iter(self.urls)

    def __len__(self) -> int:
        return len(self.urls)
