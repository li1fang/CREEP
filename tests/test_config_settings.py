import importlib


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://override-db")
    monkeypatch.setenv("LOADER_BATCH_SIZE", "5")
    monkeypatch.setenv("REDIS_URL", "redis://override:6379/1")

    from src import config

    importlib.reload(config)

    assert config.settings.database_url == "postgresql://override-db"
    assert config.settings.loader_batch_size == 5
    assert config.settings.redis_url == "redis://override:6379/1"

    monkeypatch.setenv("DATABASE_URL", "postgresql://baseline-db")
    monkeypatch.delenv("LOADER_BATCH_SIZE", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    importlib.reload(config)

    assert config.settings.loader_batch_size == 1
    assert config.settings.redis_url == "redis://localhost:6379/0"
