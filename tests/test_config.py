import importlib.util
from pathlib import Path
import pytest
from pydantic import ValidationError
from backend.core.config import Config, ROOT


@pytest.mark.parametrize("secret", ["", "short", "x" * 64, "change-me-in-production-use-env-var", "placeholder-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ", "replace-with-a-locally-generated-secret"])
def test_weak_secret_rejected(secret):
    with pytest.raises(ValidationError):
        Config(_env_file=None, JWT_SECRET_KEY=secret)


def test_offline_settings_without_gemini_key(settings):
    assert not settings.GEMINI_API_KEY.get_secret_value()
    assert settings.ENABLE_LIVE_LLM is False
    assert settings.ALLOW_MODEL_DOWNLOADS is False


def test_live_requires_key():
    with pytest.raises(ValidationError):
        Config(_env_file=None, APP_MODE="development", ENABLE_LIVE_LLM=True, GEMINI_API_KEY="")


def test_test_mode_forbids_live():
    with pytest.raises(ValidationError):
        Config(_env_file=None, ENABLE_LIVE_LLM=True, GEMINI_API_KEY="mock-not-real")


@pytest.mark.parametrize("values", [
    {"CORS_ORIGINS": ["*"]}, {"TOP_K": 11, "RETRIEVAL_K": 10},
    {"EMBEDDING_DEVICE": "gpu"}, {"MAX_LLM_CALLS_PER_TURN": 0},
    {"CORS_ORIGINS": ["https://user:password@example.org"]},
])
def test_invalid_settings(values):
    with pytest.raises(ValidationError):
        Config(_env_file=None, **values)


def test_root_env_path_and_environment_precedence(tmp_path, monkeypatch):
    env = tmp_path / "fixture.env"
    env.write_text('MODEL=file-model\nGEMINI_API_KEY=mock-file-key\n')
    monkeypatch.setenv("MODEL", "environment-model")
    settings = Config(_env_file=env)
    assert settings.MODEL == "environment-model"
    assert "mock-file-key" not in repr(settings)
    monkeypatch.chdir(tmp_path)
    assert Config(_env_file=None).DATABASE_URL == f"sqlite:///{ROOT / 'data/law.db'}"
    assert Config.model_config["env_file"] == ROOT / ".env"


def test_setup_env_preserves_existing_values(tmp_path):
    spec = importlib.util.spec_from_file_location("setup_env", ROOT / "scripts/setup_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / ".env.example").write_text((ROOT / ".env.example").read_text())
    assert module.create_env(tmp_path)
    value = (tmp_path / ".env").read_bytes()
    assert "replace-with-a-locally-generated-secret" not in value.decode()
    assert not module.create_env(tmp_path)
    assert (tmp_path / ".env").read_bytes() == value
    assert (tmp_path / ".env").stat().st_mode & 0o777 == 0o600
