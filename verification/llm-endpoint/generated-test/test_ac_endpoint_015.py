# hotdocs-criterion: sha256:207220b768bcd6c5bc93b4591d906c39bc4c7f3b9f702d5ee2212bbf5db5d1d6
import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def _toml_llm(entries):
    lines = ["[llm]"]
    for key, value in entries:
        if isinstance(value, str):
            lines.append(key + " = " + '"' + value + '"')
        else:
            lines.append(key + " = " + repr(value))
    return "\n".join(lines) + "\n"


def test_claude_cli_login_auth_loads_and_resolves(tmp_path):
    path = _write(
        tmp_path / "hotdocs.toml",
        _toml_llm([("provider", "claude-cli"), ("model", "m"), ("auth", "login")]),
    )
    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "auth") == "login"
    assert field(config, "provider") == "claude-cli"
    assert field(config, "model") == "m"

    resolved = llm_endpoint.resolve_provider("m", config)
    assert field(resolved, "auth") == "login"


def test_claude_cli_invalid_auth_value_rejected(tmp_path):
    path = _write(
        tmp_path / "hotdocs.toml",
        _toml_llm([("provider", "claude-cli"), ("model", "m"), ("auth", "token")]),
    )
    with pytest.raises(ValueError):
        llm_endpoint.load_config(path)


def test_auth_on_non_claude_cli_provider_rejected(tmp_path):
    path = _write(
        tmp_path / "hotdocs.toml",
        _toml_llm([("provider", "openai"), ("model", "m"), ("auth", "login")]),
    )
    with pytest.raises(ValueError):
        llm_endpoint.load_config(path)


def test_resolve_provider_config_without_auth_entry():
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


def test_invalid_toml_message(tmp_path):
    path = _write(tmp_path / "hotdocs.toml", "[llm\n")
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config(path)
    assert "not valid TOML" in str(excinfo.value)


def test_empty_base_url_and_api_key_env_read_as_unset(tmp_path):
    path = _write(
        tmp_path / "hotdocs.toml",
        _toml_llm(
            [
                ("provider", "openai"),
                ("model", "m"),
                ("base_url", ""),
                ("api_key_env", ""),
            ]
        ),
    )
    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "base_url") is None
    assert field(config, "api_key_env") is None


def test_save_config_with_auth_round_trips(tmp_path):
    path = tmp_path / "hotdocs.toml"
    assert not path.exists()
    llm_endpoint.save_config(path, "claude-cli", "m", auth="login")
    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "provider") == "claude-cli"
    assert field(config, "model") == "m"
    assert field(config, "auth") == "login"