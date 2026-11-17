import llm_endpoint

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(autouse=True)
def _isolated_discovery(tmp_path, monkeypatch):
    # Discovery reads VAR_HOTDOCS_CONFIG and the current directory; unset the
    # one and use a fresh other so nothing outside the test interferes.
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    yield


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_claude_cli_auth_login_loads_and_resolves(tmp_path):
    path = _write(
        tmp_path / "cfg" / "hotdocs.toml",
        '[llm]\nprovider = "claude-cli"\nmodel = "m"\nauth = "login"\n',
    )
    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "auth") == "login"
    assert field(config, "provider") == "claude-cli"
    assert field(config, "model") == "m"

    resolved = llm_endpoint.resolve_provider("m", config)
    assert field(resolved, "auth") == "login"


def test_claude_cli_auth_token_is_invalid(tmp_path):
    path = _write(
        tmp_path / "cfg" / "hotdocs.toml",
        '[llm]\nprovider = "claude-cli"\nmodel = "m"\nauth = "token"\n',
    )
    with pytest.raises(ValueError):
        llm_endpoint.load_config(path)


def test_auth_on_non_claude_cli_provider_is_invalid(tmp_path):
    path = _write(
        tmp_path / "cfg" / "hotdocs.toml",
        '[llm]\nprovider = "openai"\nmodel = "m"\nauth = "login"\n',
    )
    with pytest.raises(ValueError):
        llm_endpoint.load_config(path)


def test_resolve_provider_config_without_auth_entry_reads_auth_none():
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


def test_unparseable_file_raises_not_valid_toml(tmp_path):
    path = _write(tmp_path / "cfg" / "hotdocs.toml", "[llm\n")
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config(path)
    assert "not valid TOML" in str(excinfo.value)


def test_empty_base_url_and_api_key_env_read_as_unset(tmp_path):
    path = _write(
        tmp_path / "cfg" / "hotdocs.toml",
        '[llm]\nprovider = "openai"\nmodel = "m"\nbase_url = ""\napi_key_env = ""\n',
    )
    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "base_url") is None
    assert field(config, "api_key_env") is None


def test_save_config_with_auth_round_trips(tmp_path):
    path = tmp_path / "saved" / "hotdocs.toml"
    assert not path.exists()
    llm_endpoint.save_config(path, "claude-cli", "m", auth="login")
    assert path.exists()

    config = llm_endpoint.load_config(path)
    assert config is not None
    assert field(config, "provider") == "claude-cli"
    assert field(config, "model") == "m"
    assert field(config, "auth") == "login"