from app.config import get_settings


def test_cors_origins_parses_comma_separated_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com,http://b.com")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.cors_origins == ["http://a.com", "http://b.com"]
    finally:
        get_settings.cache_clear()


def test_cors_origins_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.cors_origins == ["http://localhost:5173"]
    finally:
        get_settings.cache_clear()
