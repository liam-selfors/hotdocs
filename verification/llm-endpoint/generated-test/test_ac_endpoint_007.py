# hotdocs-criterion: sha256:0a2135452bca27e4608fe2c632f503cf2dd7121ced6ff231dd0e590576225f70
import os
from pathlib import Path

import pytest

import llm_endpoint

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None


ENV_NAME = "VAR_HOTDOCS_CONFIG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def llm_table(entries):
    text = "[llm]\n"
    for key, value in entries:
        text = text + key + " = " + value + "\n"
    return text


FIRST = llm_table([("provider", '"openai"'), ("model", '"gpt-6-astra"')])
SECOND = llm_table([("provider", '"ollama"'), ("model", '"llama3.2"')])


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv(ENV_NAME, raising=False)
    return monkeypatch


# --- discovery -------------------------------------------------------------


def test_load_config_from_current_directory_then_named_file(tmp_path, clean_env):
    monkeypatch = clean_env
    cwd = tmp_path / "work"
    cwd.mkdir()
    write(cwd / "hotdocs.toml", FIRST)
    other = write(tmp_path / "elsewhere" / "named.toml", SECOND)
    monkeypatch.chdir(cwd)

    first = llm_endpoint.load_config()
    assert first is not None
    assert field(first, "provider") == "openai"
    assert field(first, "model") == "gpt-6-astra"
    assert field(first, "base_url") is None
    assert field(first, "api_key_env") is None
    assert field(first, "auth") is None

    monkeypatch.setenv(ENV_NAME, str(other))
    second = llm_endpoint.load_config()
    assert second is not None
    assert field(second, "provider") == "ollama"
    assert field(second, "model") == "llama3.2"


def test_load_config_returns_none_with_neither(tmp_path, clean_env):
    monkeypatch = clean_env
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    assert llm_endpoint.load_config() is None


def test_load_config_missing_named_file_raises(tmp_path, clean_env):
    monkeypatch = clean_env
    cwd = tmp_path / "work"
    cwd.mkdir()
    write(cwd / "hotdocs.toml", FIRST)
    monkeypatch.chdir(cwd)
    monkeypatch.setenv(ENV_NAME, str(tmp_path / "does-not-exist.toml"))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


# --- invalid tables --------------------------------------------------------


INVALID_CASES = [
    (
        "unknown_entry",
        llm_table(
            [
                ("provider", '"openai"'),
                ("model", '"gpt-6-astra"'),
                ("colour", '"blue"'),
            ]
        ),
        ["colour"],
    ),
    (
        "bad_provider",
        llm_table([("provider", '"frobnicator"'), ("model", '"m1"')]),
        ["frobnicator", "provider"],
    ),
    (
        "no_model",
        llm_table([("provider", '"openai"')]),
        ["model"],
    ),
    (
        "short_timeout",
        llm_table(
            [
                ("provider", '"openai"'),
                ("model", '"gpt-6-astra"'),
                ("timeout_seconds", "120"),
            ]
        ),
        ["timeout_seconds", "timeout", "300"],
    ),
    (
        "claude_cli_base_url",
        llm_table(
            [
                ("provider", '"claude-cli"'),
                ("model", '"claude-sonnet-5"'),
                ("base_url", '"https://example.invalid"'),
            ]
        ),
        ["base_url"],
    ),
]


@pytest.mark.parametrize(
    "name,text,tokens", INVALID_CASES, ids=[c[0] for c in INVALID_CASES]
)
def test_load_config_rejects_invalid_table(tmp_path, clean_env, name, text, tokens):
    monkeypatch = clean_env
    monkeypatch.chdir(tmp_path)
    path = write(tmp_path / "configs" / (name + ".toml"), text)
    with pytest.raises(ValueError) as info:
        llm_endpoint.load_config(path)
    message = str(info.value)
    assert message.strip() != ""
    lowered = message.lower()
    assert any(token.lower() in lowered for token in tokens), message


def test_load_config_rejects_api_key_entry_as_secret(tmp_path, clean_env):
    monkeypatch = clean_env
    monkeypatch.chdir(tmp_path)
    text = llm_table(
        [
            ("provider", '"openai"'),
            ("model", '"gpt-6-astra"'),
            ("api_key", '"sk-not-a-real-key-123456"'),
        ]
    )
    path = write(tmp_path / "configs" / "secret.toml", text)
    with pytest.raises(ValueError) as info:
        llm_endpoint.load_config(path)
    message = str(info.value)
    assert "must never hold a secret" in message
    assert "hotdocs.toml" in message


# --- save_config -----------------------------------------------------------


def test_save_config_replaces_llm_and_keeps_other(tmp_path, clean_env):
    monkeypatch = clean_env
    monkeypatch.chdir(tmp_path)
    secret_value = "sk-ant-fake-secret-value-0123456789"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret_value)

    original = (
        FIRST
        + "\n[other]\n"
        + "name = \"keep-me\"\n"
        + "count = 3\n"
        + "flags = [\"a\", \"b\"]\n"
    )
    path = write(tmp_path / "hotdocs.toml", original)

    if tomllib is not None:
        before_other = tomllib.loads(original)["other"]
    else:
        before_other = None

    llm_endpoint.save_config(
        path,
        "anthropic",
        "claude-sonnet-5",
        api_key_env="ANTHROPIC_API_KEY",
    )

    written = path.read_text(encoding="utf-8")
    assert secret_value not in written

    loaded = llm_endpoint.load_config(path)
    assert loaded is not None
    assert field(loaded, "provider") == "anthropic"
    assert field(loaded, "model") == "claude-sonnet-5"
    assert field(loaded, "api_key_env") == "ANTHROPIC_API_KEY"

    if tomllib is not None:
        data = tomllib.loads(written)
        assert data["other"] == before_other
        llm = data["llm"]
        assert llm["provider"] == "anthropic"
        assert llm["model"] == "claude-sonnet-5"
        for key in llm:
            lowered = key.lower()
            assert lowered not in ("api_key", "token", "password", "secret")
        for value in llm.values():
            assert value != secret_value
    else:
        assert "[other]" in written
        assert "keep-me" in written
        assert "openai" not in written