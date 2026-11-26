# hotdocs-criterion: sha256:2baa16dc90c345341c71386314174226a96adfa962452500b57a676c15a160c2
import os
from pathlib import Path

import pytest

import llm_endpoint

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FIRST_TOML = (
    "[llm]\n"
    'provider = "openai"\n'
    'model = "gpt-6-astra"\n'
    'api_key_env = "OPENAI_API_KEY"\n'
    "timeout_seconds = 600\n"
)

SECOND_TOML = (
    "[llm]\n"
    'provider = "ollama"\n'
    'model = "llama3.2"\n'
    'base_url = "http://localhost:11434"\n'
)


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def test_discovery_order(clean_env, monkeypatch, tmp_path):
    work = clean_env
    (work / "hotdocs.toml").write_text(FIRST_TOML)

    first = llm_endpoint.load_config()
    assert first is not None
    assert field(first, "provider") == "openai"
    assert field(first, "model") == "gpt-6-astra"
    assert field(first, "api_key_env") == "OPENAI_API_KEY"
    assert field(first, "timeout_seconds") == 600
    assert field(first, "base_url") is None
    assert field(first, "auth") is None

    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    other = other_dir / "named.toml"
    other.write_text(SECOND_TOML)
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(other))

    second = llm_endpoint.load_config()
    assert second is not None
    assert field(second, "provider") == "ollama"
    assert field(second, "model") == "llama3.2"
    assert field(second, "base_url") == "http://localhost:11434"
    assert field(second, "api_key_env") is None
    assert field(second, "auth") is None

    # Neither: no env var, no hotdocs.toml in cwd.
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    (work / "hotdocs.toml").unlink()
    assert llm_endpoint.load_config() is None

    # A named file that is missing is an error.
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(other_dir / "missing.toml"))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    return p


@pytest.mark.parametrize(
    "name,body,needles",
    [
        (
            "unknown",
            '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\ncolourful_flag = "blue"\n',
            ["colourful_flag"],
        ),
        (
            "provider",
            '[llm]\nprovider = "bogusprov"\nmodel = "x-model"\n',
            ["bogusprov", "provider"],
        ),
        (
            "nomodel",
            '[llm]\nprovider = "openai"\n',
            ["model"],
        ),
        (
            "timeout",
            '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\ntimeout_seconds = 120\n',
            ["timeout"],
        ),
        (
            "cli_base_url",
            '[llm]\nprovider = "claude-cli"\nmodel = "claude-sonnet-5"\nbase_url = "https://example.invalid"\n',
            ["base_url"],
        ),
    ],
)
def test_invalid_tables_raise(clean_env, tmp_path, name, body, needles):
    path = _write(tmp_path, name + ".toml", body)
    with pytest.raises(ValueError) as exc:
        llm_endpoint.load_config(path)
    msg = str(exc.value).lower()
    assert any(n.lower() in msg for n in needles), msg


def test_api_key_entry_is_secret(clean_env, tmp_path):
    path = _write(
        tmp_path,
        "secret.toml",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\napi_key = "sk-abc123def456"\n',
    )
    with pytest.raises(ValueError) as exc:
        llm_endpoint.load_config(path)
    msg = str(exc.value)
    assert "must never hold a secret" in msg
    assert "hotdocs.toml" in msg


def test_save_config_replaces_only_llm(clean_env, monkeypatch, tmp_path):
    secret_value = "sk-ant-supersecret-value-0123456789"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret_value)
    path = tmp_path / "cfg" / "hotdocs.toml"
    path.parent.mkdir()
    path.write_text(
        FIRST_TOML
        + "\n[other]\n"
        + 'name = "keep-me"\n'
        + "numbers = [1, 2, 3]\n"
    )

    llm_endpoint.save_config(
        path, "anthropic", "claude-sonnet-5", api_key_env="ANTHROPIC_API_KEY"
    )

    text = path.read_text()
    assert secret_value not in text

    loaded = llm_endpoint.load_config(path)
    assert loaded is not None
    assert field(loaded, "provider") == "anthropic"
    assert field(loaded, "model") == "claude-sonnet-5"
    assert field(loaded, "api_key_env") == "ANTHROPIC_API_KEY"

    if tomllib is not None:
        data = tomllib.loads(text)
        assert data["other"] == {"name": "keep-me", "numbers": [1, 2, 3]}
        assert data["llm"]["provider"] == "anthropic"
        assert data["llm"]["model"] == "claude-sonnet-5"
        for key in data["llm"]:
            lowered = key.lower()
            assert lowered == "api_key_env" or not any(
                s in lowered for s in ("api_key", "token", "password", "secret")
            )
    else:
        assert "[other]" in text
        assert 'name = "keep-me"' in text