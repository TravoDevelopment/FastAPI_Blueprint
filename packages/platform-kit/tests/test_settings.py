import pytest
from pydantic import ValidationError

from platform_kit.settings import ServiceSettings


def test_development_allows_defaults() -> None:
    settings = ServiceSettings(ENVIRONMENT="development")
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_deployed_environment_rejects_insecure_defaults() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        ServiceSettings(ENVIRONMENT="production")


def test_deployed_environment_accepts_real_values() -> None:
    settings = ServiceSettings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="a-real-random-secret-key-of-at-least-32-chars",
        DB_PASSWORD="a-real-password",
        PROBLEM_TYPE_BASE_URI="https://errors.mycompany.com",
    )
    assert settings.is_deployed


def test_service_settings_accept_identity_secret_key_name() -> None:
    settings = ServiceSettings(_env_file=None, SECRET_KEY="identity-shared-secret-key-of-at-least-32-chars")
    assert settings.JWT_SECRET_KEY.get_secret_value() == "identity-shared-secret-key-of-at-least-32-chars"


def test_jwt_secret_key_takes_precedence_over_identity_secret_key() -> None:
    settings = ServiceSettings(
        _env_file=None,
        JWT_SECRET_KEY="service-specific-jwt-secret-of-at-least-32-chars",
        SECRET_KEY="identity-shared-secret-key-of-at-least-32-chars",
    )
    assert settings.JWT_SECRET_KEY.get_secret_value() == "service-specific-jwt-secret-of-at-least-32-chars"
