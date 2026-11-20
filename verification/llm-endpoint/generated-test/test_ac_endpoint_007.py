# hotdocs-criterion: sha256:47c2fb5182c421c13941ab5721c5a47ad2e77011d7315322a95f98b51c0ea5f3
import os
import sys

import pytest

import llm_endpoint

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None


ALLOWED_KEYS = {"provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def test_discovery_cwd_then_named_then_none_and_missing_named_raises(clean_env, tmp_path, monkeypatch):
    cwd = clean_env
    write(
        cwd / "hotdocs.toml",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\n',
    )
    other = write(
        tmp_path / "elsewhere" / "named.toml",
        '[llm]\nprovider = "anthropic"\nmodel = "claude-sonnet-5"\n',
    )

    first = llm_endpoint.load_config()
    assert first is not None
    assert field(first, "provider") == "openai"
    assert field(first, "model") == "gpt-6-astra"

    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(other))
    second = llm_endpoint.load_config()
    assert second is not None
    assert field(second, "provider") == "anthropic"
    assert field(second, "model") == "claude-sonnet-5"

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    (cwd / "hotdocs.toml").unlink()
    assert llm_endpoint.load_config() is None

    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(tmp_path / "elsewhere" / "missing.toml"))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


@pytest.mark.parametrize(
    "body, expected",
    [
        ('provider = "openai"\nmodel = "gpt-6-astra"\ncolour = "blue"\n', "colour"),
        ('provider = "openai"\nmodel = "gpt-6-astra"\napi_key = "sk-test-pasted-123"\n', "must never hold a secret"),
        ('provider = "notaprovider"\nmodel = "gpt-6-astra"\n', "provider"),
        ('provider = "openai"\n', "model"),
        ('provider = "openai"\nmodel = "gpt-6-astra"\ntimeout_seconds = 120\n', "timeout_seconds"),
        ('provider = "claude-cli"\nmodel = "claude-sonnet-5"\nbase_url = "https://example.invalid"\n', "base_url"),
    ],
    ids=["unknown-entry", "api-key", "bad-provider", "no-model", "timeout-120", "claude-cli-base-url"],
)
def test_invalid_llm_tables_raise_value_error_naming_problem(clean_env, tmp_path, body, expected):
    path = write(tmp_path / "bad" / "hotdocs.toml", "[llm]\n" + body)
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config(path)
    assert expected in str(excinfo.value)


@pytest.mark.skipif(tomllib is None, reason="tomllib requires Python 3.11+")
def test_save_config_replaces_llm_keeps_other_and_holds_no_secret(clean_env, tmp_path, monkeypatch):
    secret = "sk-ant-secret-value-xyz-987654"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    path = write(
        tmp_path / "proj" / "hotdocs.toml",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\napi_key_env = "OPENAI_API_KEY"\n'
        '\n[other]\nname = "keep"\nvalue = 3\n',
    )
    before = tomllib.loads(path.read_text(encoding="utf-8"))
    other_before = before["other"]

    llm_endpoint.save_config(path, "anthropic", "claude-sonnet-5", api_key_env="ANTHROPIC_API_KEY")

    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)

    assert data["other"] == other_before
    assert data["other"] == {"name": "keep", "value": 3}

    llm = data["llm"]
    assert llm["provider"] == "anthropic"
    assert llm["model"] == "claude-sonnet-5"
    assert set(llm.keys()) <= ALLOWED_KEYS
    for key in llm.keys():
        assert key not in ("api_key", "token", "password", "secret")

    assert secret not in text

    loaded = llm_endpoint.load_config(path)
    assert loaded is not None
    assert field(loaded, "provider") == "anthropic"
    assert field(loaded, "model") == "claude-sonnet-5"