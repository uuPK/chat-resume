"""用于覆盖 test_config_security.py 对应的回归测试。"""

from __future__ import annotations

import pytest

from app.infra.config import DEFAULT_SECRET_KEY, Settings, validate_secret_key


def test_production_rejects_default_secret_key():
    """用于验证productionrejectsdefaultsecretkey。"""
    settings = Settings.model_validate(
        {
            "APP_ENV": "production",
            "SECRET_KEY": DEFAULT_SECRET_KEY,
        }
    )

    with pytest.raises(ValueError, match="SECRET_KEY"):
        validate_secret_key(settings)


def test_production_accepts_explicit_secret_key():
    """用于验证productionacceptsexplicitsecretkey。"""
    settings = Settings.model_validate(
        {
            "APP_ENV": "production",
            "SECRET_KEY": "prod-secret-key-with-at-least-32-characters",
        }
    )

    validate_secret_key(settings)


def test_development_allows_default_secret_key():
    """用于验证developmentallowsdefaultsecretkey。"""
    settings = Settings.model_validate(
        {
            "APP_ENV": "development",
            "SECRET_KEY": DEFAULT_SECRET_KEY,
        }
    )

    validate_secret_key(settings)
