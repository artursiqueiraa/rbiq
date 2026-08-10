from app.core.config import Settings, get_settings


def test_settings_load_with_defaults():
    settings = Settings(_env_file=None)

    assert settings.app_name == "IQO Strategy Lab"
    assert settings.api_port == 8000
    assert settings.database_url.startswith("postgresql")


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
