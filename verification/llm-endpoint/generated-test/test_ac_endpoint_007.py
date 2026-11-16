"""AC-ENDPOINT-007: hotdocs.toml discovery, validation, and save_config.

Covers R-ENDPOINT-007.
"""
import os
from pathlib import Path

import pytest

import llm_endpoint

try:  # Python 3.11+
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover - older interpreters
    tomllib = None


ENV_NAME = "VAR_HOTDOCS_CONFIG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """A fresh current directory with VAR_HOTDOCS_CONFIG unset."""
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.delenv(ENV_NAME, raising=False)
    monkeypatch.chdir(workdir)
    return workdir


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_discovery_cwd_then_named_file_then_none_and_missing_named_file(
    isolated, tmp_path, monkeypatch
):
    cwd_file = isolated / "hotdocs.toml"
    cwd_file.write_text(
        "[llm]\n"
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        'api_key_env = "OPENAI_API_KEY"\n',
        encoding="utf-8",
    )

    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    named_file = other_dir / "custom-config.toml"
    named_file.write_text(
        "[llm]\n"
        'provider = "ollama"\n'
        'model = "llama3.1:8b"\n'
        'base_url = "http://localhost:11434"\n'
        "timeout_seconds = 900\n",
        encoding="utf-8",
    )

    # 1. The current directory's hotdocs.toml.
    first = llm_endpoint.load_config()
    assert first is not None
    assert field(first, "provider") == "openai"
    assert field(first, "model") == "gpt-6-astra"
    assert field(first, "api_key_env") == "OPENAI_API_KEY"

    # 2. VAR-HOTDOCS-CONFIG naming another valid file wins.
    monkeypatch.setenv(ENV_NAME, str(named_file))
    second = llm_endpoint.load_config()
    assert second is not None
    assert field(second, "provider") == "ollama"
    assert field(second, "model") == "llama3.1:8b"
    assert field(second, "base_url") == "http://localhost:11434"
    assert field(second, "timeout_seconds") == 900

    # 3. Neither: no variable, no hotdocs.toml in the current directory.
    monkeypatch.delenv(ENV_NAME, raising=False)
    cwd_file.unlink()
    assert not (Path.cwd() / "hotdocs.toml").exists()
    assert llm_endpoint.load_config() is None

    # 4. A named file that is missing is an error.
    missing = tmp_path / "does-not-exist.toml"
    assert not missing.exists()
    monkeypatch.setenv(ENV_NAME, str(missing))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


INVALID_CASES = [
    (
        "unknown-entry",
        "[llm]\n"
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        'colour = "blue"\n',
        ["colour"],
    ),
    (
        "api-key-entry",
        "[llm]\n"
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        'api_key = "sk-test-not-a-real-key-0000"\n',
        ["must never hold a secret"],
    ),
    (
        "unknown-provider",
        "[llm]\n"
        'provider = "frobnicator"\n'
        'model = "some-model"\n',
        ["provider", "frobnicator"],
    ),
    (
        "no-model",
        "[llm]\n"
        'provider = "openai"\n',
        ["model"],
    ),
    (
        "timeout-too-small",
        "[llm]\n"
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        "timeout_seconds = 120\n",
        ["timeout"],
    ),
    (
        "claude-cli-with-base-url",
        "[llm]\n"
        'provider = "claude-cli"\n'
        'model = "claude-sonnet-5"\n'
        'base_url = "https://example.invalid"\n',
        ["base_url"],
    ),
]


@pytest.mark.parametrize(
    "content,expected_any",
    [(c, e) for _, c, e in INVALID_CASES],
    ids=[name for name, _, _ in INVALID_CASES],
)
def test_invalid_llm_tables_raise_value_error_naming_problem(
    isolated, content, expected_any
):
    cfg = isolated / "hotdocs.toml"
    cfg.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config()

    message = str(excinfo.value)
    lowered = message.lower()
    assert any(token.lower() in lowered for token in expected_any), (
        f"ValueError message {message!r} does not name the problem "
        f"(expected one of {expected_any!r})"
    )


def test_api_key_entry_message_says_never_hold_a_secret(isolated):
    cfg = isolated / "hotdocs.toml"
    cfg.write_text(
        "[llm]\n"
        'provider = "anthropic"\n'
        'model = "claude-sonnet-5"\n'
        'api_key = "sk-ant-test-not-real-1111"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config(cfg)
    message = str(excinfo.value)
    assert "must never hold a secret" in message
    assert "sk-ant-test-not-real-1111" not in message


# ---------------------------------------------------------------------------
# save_config
# ---------------------------------------------------------------------------


def test_save_config_replaces_llm_only_and_writes_no_secret(isolated, monkeypatch):
    secret_value = "sk-ant-very-secret-value-9f8e7d6c5b4a"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret_value)

    cfg = isolated / "hotdocs.toml"
    cfg.write_text(
        "[llm]\n"
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        'api_key_env = "OPENAI_API_KEY"\n'
        "\n"
        "[other]\n"
        'name = "keep me"\n'
        "flag = true\n"
        "count = 7\n",
        encoding="utf-8",
    )

    llm_endpoint.save_config(
        cfg,
        "anthropic",
        "claude-sonnet-5",
        api_key_env="ANTHROPIC_API_KEY",
    )

    text = cfg.read_text(encoding="utf-8")

    # The new [llm] is written.
    loaded = llm_endpoint.load_config(cfg)
    assert loaded is not None
    assert field(loaded, "provider") == "anthropic"
    assert field(loaded, "model") == "claude-sonnet-5"
    assert field(loaded, "api_key_env") == "ANTHROPIC_API_KEY"

    # The file never contains a secret.
    assert secret_value not in text

    if tomllib is not None:
        parsed = tomllib.loads(text)
        # [other] is untouched.
        assert parsed.get("other") == {"name": "keep me", "flag": True, "count": 7}
        llm = parsed["llm"]
        assert llm["provider"] == "anthropic"
        assert llm["model"] == "claude-sonnet-5"
        allowed = {"provider", "model", "base_url", "api_key_env", "timeout_seconds"}
        assert set(llm) <= allowed
        for key in llm:
            assert key in ("api_key_env",) or not any(
                s in key.lower() for s in ("api_key", "token", "password", "secret")
            )
        for value in llm.values():
            assert value != secret_value
    else:  # pragma: no cover
        assert "[other]" in text
        assert 'name = "keep me"' in text
        assert "flag = true" in text
        assert "count = 7" in text
        assert 'provider = "anthropic"' in text
        assert 'provider = "openai"' not in text