# hotdocs-criterion: sha256:d77b6a6cc8b92e63196d386fe00a5a28661fa2bf48ef3e8f89b5e0d448672363
import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    yield


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _llm_table(**entries):
    lines = ["[llm]"]
    for key, value in entries.items():
        lines.append(key + " = " + '"' + value + '"')
    return "\n".join(lines) + "\n"


def test_claude_cli_login_auth_loads_and_resolves(tmp_path):
    path = _write(
        tmp_path / "a" / "hotdocs.toml",
        _llm_table(provider="claude-cli", model="m", auth="login"),
    )
    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "auth") == "login"

    resolved = llm_endpoint.resolve_provider("m", config)
    assert field(resolved, "auth") == "login"


def test_claude_cli_invalid_auth_value_raises(tmp_path):
    path = _write(
        tmp_path / "b" / "hotdocs.toml",
        _llm_table(provider="claude-cli", model="m", auth="token"),
    )
    with pytest.raises(ValueError):
        llm_endpoint.load_config(path)


def test_auth_on_non_claude_cli_provider_raises(tmp_path):
    path = _write(
        tmp_path / "c" / "hotdocs.toml",
        _llm_table(provider="openai", model="m", auth="login"),
    )
    with pytest.raises(ValueError):
        llm_endpoint.load_config(path)


def test_resolve_provider_with_config_lacking_auth():
    config = {
        "provider": "openai",
        "model": "x",
        "base_url": None,
        "api_key_env": "MY_KEY",
        "timeout_seconds": 400,
    }
    resolved = llm_endpoint.resolve_provider("gpt-6-astra", config)
    assert field(resolved, "provider") == "openai"
    assert field(resolved, "api_key_env") == "MY_KEY"
    assert field(resolved, "timeout_seconds") == 400
    assert field(resolved, "auth") is None


def test_invalid_toml_raises_with_message(tmp_path):
    path = _write(tmp_path / "d" / "hotdocs.toml", "[llm\n")
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config(path)
    assert "not valid TOML" in str(excinfo.value)


def test_empty_base_url_and_api_key_env_read_as_unset(tmp_path):
    path = _write(
        tmp_path / "e" / "hotdocs.toml",
        _llm_table(provider="openai", model="m", base_url="", api_key_env=""),
    )
    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "base_url") is None
    assert field(config, "api_key_env") is None


def test_save_config_then_load_round_trips_auth(tmp_path):
    path = tmp_path / "f" / "hotdocs.toml"
    assert not path.exists()
    llm_endpoint.save_config(path, "claude-cli", "m", auth="login")
    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "provider") == "claude-cli"
    assert field(config, "model") == "m"
    assert field(config, "auth") == "login"