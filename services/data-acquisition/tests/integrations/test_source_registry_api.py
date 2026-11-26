"""Exercise the Source Registry API against PostgreSQL and the real access check."""

from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from httpx import AsyncClient

BASE = "/v1/sources"
SOURCE_URL = "https://example.com/places"
ClientFactory = Callable[..., Awaitable[AsyncClient]]


async def test_sign_in_is_required(client: ClientFactory) -> None:
    """Anonymous callers cannot list sources."""
    http = await client()
    assert (await http.get(f"{BASE}/")).status_code == 401


async def test_caller_without_a_grant_is_refused(client: ClientFactory, deny_access: Callable[[], None]) -> None:
    """Signed-in callers still need a grant for the requested operation."""
    deny_access()
    http = await client(user_id=uuid4())
    response = await http.get(f"{BASE}/")
    assert response.status_code == 403
    assert response.json()["code"] == "access_denied"


async def test_full_lifecycle(client: ClientFactory) -> None:
    """The shipped policy permits the registered, enabled, disabled, and deleted lifecycle."""
    creator_id = uuid4()
    http = await client(user_id=creator_id)
    created = await http.post(
        f"{BASE}/", json={"name": "Travel Guide", "description": "Travel listings", "sourceUrls": [SOURCE_URL]}
    )
    assert created.status_code == 201, created.text
    source = created.json()
    assert source["isEnabled"] is False
    assert source["createdBy"] == source["updatedBy"] == str(creator_id)
    url = f"{BASE}/{source['id']}"
    assert created.headers["Location"] == url

    fetched = await http.get(url)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == source
    listed = await http.get(f"{BASE}/", params={"isEnabled": "false", "name": "guide"})
    assert listed.status_code == 200, listed.text
    assert listed.json()["sources"] == [source]
    assert listed.json()["pageInfo"]["totalCount"] == 1

    editor_id = uuid4()
    http = await client(user_id=editor_id)
    renamed = await http.patch(url, json={"name": "Updated Guide"})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Updated Guide"
    assert renamed.json()["description"] == "Travel listings"
    assert renamed.json()["createdBy"] == str(creator_id)
    assert renamed.json()["updatedBy"] == str(editor_id)

    cleared = await http.patch(url, json={"description": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["description"] is None

    enabled = await http.post(f"{url}:enable")
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["isEnabled"] is True
    assert enabled.json()["updatedBy"] == str(editor_id)
    blocked = await http.delete(url)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "source_must_be_disabled"

    http = await client(user_id=creator_id)
    disabled = await http.post(f"{url}:disable")
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["isEnabled"] is False
    assert disabled.json()["updatedBy"] == str(creator_id)
    assert (await http.delete(url)).status_code == 204
    gone = await http.get(url)
    assert gone.status_code == 404
    assert gone.json()["code"] == "source_not_found"


async def test_duplicate_name_is_a_409(client: ClientFactory) -> None:
    """Normalized names cannot be reused, even with different capitalization."""
    http = await client(user_id=uuid4())
    created = await http.post(f"{BASE}/", json={"name": "Travel Guide", "sourceUrls": [SOURCE_URL]})
    assert created.status_code == 201, created.text
    response = await http.post(f"{BASE}/", json={"name": "travel guide", "sourceUrls": [SOURCE_URL]})
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "source_name_taken"


async def test_max_length_unicode_names_with_expanding_casefold(client: ClientFactory) -> None:
    """Create and patch preserve 120-character names and reject collisions on their expanded keys."""
    http = await client(user_id=uuid4())
    name = "ß" * 120
    equivalent_name = "ẞ" * 120
    renamed_name = "A" + "ß" * 119

    created = await http.post(f"{BASE}/", json={"name": name, "sourceUrls": [SOURCE_URL]})
    assert created.status_code == 201, created.text
    assert created.json()["name"] == name
    duplicate = await http.post(f"{BASE}/", json={"name": equivalent_name, "sourceUrls": [SOURCE_URL]})
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "source_name_taken"

    other = await http.post(f"{BASE}/", json={"name": "Other Guide", "sourceUrls": [SOURCE_URL]})
    assert other.status_code == 201, other.text
    url = other.headers["Location"]
    conflict = await http.patch(url, json={"name": equivalent_name})
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["code"] == "source_name_taken"

    renamed = await http.patch(url, json={"name": renamed_name})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == renamed_name
    fetched = await http.get(url)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["name"] == renamed_name


@pytest.mark.parametrize("source_url", ["http://example.com/places", "https://[2001:db8::1/places"])
async def test_invalid_url_is_a_422(client: ClientFactory, source_url: str) -> None:
    """Registration returns Problem Details for non-HTTPS URLs and malformed bracketed HTTPS authorities."""
    http = await client(user_id=uuid4())
    response = await http.post(f"{BASE}/", json={"name": "Travel Guide", "sourceUrls": [source_url]})
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].split(";", 1)[0] == "application/problem+json"
    assert response.json()["code"] == "invalid_source_url"
    assert response.json()["status"] == 422


@pytest.mark.parametrize("field", ["name", "sourceUrls", "source_urls"])
async def test_patch_rejects_explicit_null_with_another_valid_field(client: ClientFactory, field: str) -> None:
    """An explicit null name or URL list rejects the entire patch, even with a valid description."""
    http = await client(user_id=uuid4())
    created = await http.post(
        f"{BASE}/", json={"name": "Travel Guide", "description": "Original description", "sourceUrls": [SOURCE_URL]}
    )
    assert created.status_code == 201, created.text
    url = created.headers["Location"]
    response = await http.patch(url, json={field: None, "description": "Updated description"})
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].split(";", 1)[0] == "application/problem+json"
    assert response.json()["status"] == 422

    fetched = await http.get(url)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == created.json()


@pytest.mark.parametrize("wildcard", ["%", "_"])
async def test_name_filter_treats_sql_wildcards_as_literals(client: ClientFactory, wildcard: str) -> None:
    """A percent sign or underscore in the name filter matches only that literal character."""
    http = await client(user_id=uuid4())
    matching = await http.post(f"{BASE}/", json={"name": f"Travel{wildcard}Guide", "sourceUrls": [SOURCE_URL]})
    assert matching.status_code == 201, matching.text
    decoy = await http.post(f"{BASE}/", json={"name": "Travel Guide", "sourceUrls": [SOURCE_URL]})
    assert decoy.status_code == 201, decoy.text

    response = await http.get(f"{BASE}/", params={"name": f"L{wildcard}G"})
    assert response.status_code == 200, response.text
    assert response.json()["sources"] == [matching.json()]
    assert response.json()["pageInfo"]["totalCount"] == 1


async def test_openapi_documents_problem_details_and_creation_location(client: ClientFactory) -> None:
    """Every source operation documents applicable Problem Details, and registration documents Location."""
    http = await client()
    response = await http.get("/openapi.json")
    assert response.status_code == 200, response.text
    paths = response.json()["paths"]
    operations = {
        (f"{BASE}/", "get"): (),
        (f"{BASE}/", "post"): ("409",),
        (f"{BASE}/{{source_id}}", "get"): ("404",),
        (f"{BASE}/{{source_id}}", "patch"): ("404", "409"),
        (f"{BASE}/{{source_id}}", "delete"): ("404", "409"),
        (f"{BASE}/{{source_id}}:enable", "post"): ("404", "409"),
        (f"{BASE}/{{source_id}}:disable", "post"): ("404", "409"),
    }
    for (path, method), additional_codes in operations.items():
        responses = paths[path][method]["responses"]
        for code in ("401", "403", "422", "429", *additional_codes):
            assert code in responses, (method, path, code)
            assert set(responses[code]["content"]) == {"application/problem+json"}, (method, path, code)

    created = paths[f"{BASE}/"]["post"]["responses"]["201"]
    assert created["headers"]["Location"]["schema"]["type"] == "string"
