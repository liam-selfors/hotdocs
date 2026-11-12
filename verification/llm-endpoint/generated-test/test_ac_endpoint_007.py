import os
from pathlib import Path

import pytest

import llm_endpoint

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None


ENV_NAME = "VAR_HOTDOCS_CONFIG"


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


FIRST_TOML = """\
[llm]
provider = "openai"
model = "gpt-6-astra"
timeout_seconds = 600
"""

SECOND_TOML = """\
[llm]
provider = "ollama"
model = "llama3.2"
base_url = "http://localhost:11434"
timeout_seconds = 900
"""


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_NAME, raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return workdir


def test_discovery_current_directory_then_named_file_then_none(clean_env, monkeypatch, tmp_path):
    workdir = clean_env
    _write(workdir / "hotdocs.toml", FIRST_TOML)

    first = llm_endpoint.load_config()
    assert first is not None
    assert _get(first, "provider") == "openai"
    assert _get(first, "model") == "gpt-6-astra"
    assert _get(first, "timeout_seconds") == 600

    named = _write(tmp_path / "elsewhere" / "named.toml", SECOND_TOML)
    monkeypatch.setenv(ENV_NAME, str(named))
    second = llm_endpoint.load_config()
    assert second is not None
    assert _get(second, "provider") == "ollama"
    assert _get(second, "model") == "llama3.2"
    assert _get(second, "timeout_seconds") == 900

    # Neither: env var unset and a fresh directory with no hotdocs.toml.
    monkeypatch.delenv(ENV_NAME, raising=False)
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)
    assert llm_endpoint.load_config() is None


def test_named_missing_file_raises_value_error(clean_env, monkeypatch, tmp_path):
    workdir = clean_env
    # Even with a valid file in the current directory, a named missing file is an error.
    _write(workdir / "hotdocs.toml", FIRST_TOML)
    missing = tmp_path / "does-not-exist" / "hotdocs.toml"
    assert not missing.exists()
    monkeypatch.setenv(ENV_NAME, str(missing))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


INVALID_CASES = [
    (
        "unknown_entry",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\nflavour_of_the_day = "x"\n',
        ["flavour_of_the_day"],
    ),
    (
        "provider_outside_list",
        '[llm]\nprovider = "not-a-real-provider"\nmodel = "some-model"\n',
        ["provider", "not-a-real-provider"],
    ),
    (
        "no_model",
        '[llm]\nprovider = "openai"\n',
        ["model"],
    ),
    (
        "timeout_too_small",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\ntimeout_seconds = 120\n',
        ["timeout", "300", "120"],
    ),
    (
        "claude_cli_with_base_url",
        '[llm]\nprovider = "claude-cli"\nmodel = "claude-sonnet-5"\nbase_url = "https://example.invalid"\n',
        ["base_url"],
    ),
]


@pytest.mark.parametrize("name,text,expected_any", INVALID_CASES, ids=[c[0] for c in INVALID_CASES])
def test_invalid_llm_tables_raise_value_error_naming_problem(clean_env, tmp_path, name, text, expected_any):
    path = _write(tmp_path / "cfg" / f"{name}.toml", text)
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config(path)
    message = str(excinfo.value)
    assert any(token in message for token in expected_any), (
        f"message {message!r} does not name the problem (expected one of {expected_any})"
    )


def test_api_key_entry_rejected_as_secret(clean_env, tmp_path):
    path = _write(
        tmp_path / "cfg" / "api_key.toml",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\napi_key = "sk-pasted-secret-value-xyz"\n',
    )
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config(path)
    message = str(excinfo.value)
    assert "must never hold a secret" in message
    assert "sk-pasted-secret-value-xyz" not in message


def test_save_config_replaces_llm_and_preserves_other_table(clean_env, monkeypatch, tmp_path):
    secret_value = "sk-ant-super-secret-test-value-0123456789"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret_value)

    original = (
        '[llm]\n'
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        'api_key_env = "OPENAI_API_KEY"\n'
        '\n'
        '[other]\n'
        'name = "keep me"\n'
        'count = 3\n'
    )
    path = _write(tmp_path / "proj" / "hotdocs.toml", original)

    llm_endpoint.save_config(
        path,
        "anthropic",
        "claude-sonnet-5",
        api_key_env="ANTHROPIC_API_KEY",
        timeout_seconds=600,
    )

    content = path.read_text(encoding="utf-8")

    # Never contains a secret.
    assert secret_value not in content

    loaded = llm_endpoint.load_config(path)
    assert loaded is not None
    assert _get(loaded, "provider") == "anthropic"
    assert _get(loaded, "model") == "claude-sonnet-5"
    assert _get(loaded, "api_key_env") == "ANTHROPIC_API_KEY"
    assert _get(loaded, "timeout_seconds") == 600

    if tomllib is not None:
        parsed = tomllib.loads(content)
        assert parsed.get("other") == {"name": "keep me", "count": 3}
        llm = parsed.get("llm")
        assert isinstance(llm, dict)
        assert llm.get("provider") == "anthropic"
        assert llm.get("model") == "claude-sonnet-5"
        for key in llm:
            lowered = key.lower()
            assert lowered == "api_key_env" or not any(
                word in lowered for word in ("api_key", "token", "password", "secret")
            ), f"[llm] holds a secret-like entry {key!r}"
        for value in llm.values():
            assert value != secret_value
    else:
        assert "[other]" in content
        assert 'name = "keep me"' in content
        assert "count = 3" in content
        assert "gpt-6-astra" not in content
        assert "\napi_key =" not in content