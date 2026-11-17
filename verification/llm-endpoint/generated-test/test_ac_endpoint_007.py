import llm_endpoint

import os

import pytest

try:
    import tomllib
except ImportError:  # pragma: no cover - Python < 3.11
    tomllib = None


ENV_NAME = "VAR_HOTDOCS_CONFIG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_NAME, raising=False)
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return workdir


# ---------------------------------------------------------------------------
# Scenario 1: discovery
# ---------------------------------------------------------------------------


def test_discovery_cwd_then_named_file_then_none(clean_env, monkeypatch, tmp_path):
    _write(
        clean_env / "hotdocs.toml",
        '[llm]\n'
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        'api_key_env = "OPENAI_API_KEY"\n'
        'timeout_seconds = 600\n',
    )

    first = llm_endpoint.load_config()
    assert first is not None
    assert field(first, "provider") == "openai"
    assert field(first, "model") == "gpt-6-astra"
    assert field(first, "api_key_env") == "OPENAI_API_KEY"
    assert field(first, "timeout_seconds") == 600

    other = _write(
        tmp_path / "elsewhere" / "named.toml",
        '[llm]\n'
        'provider = "anthropic"\n'
        'model = "claude-sonnet-5"\n',
    )
    monkeypatch.setenv(ENV_NAME, str(other))

    second = llm_endpoint.load_config()
    assert second is not None
    assert field(second, "provider") == "anthropic"
    assert field(second, "model") == "claude-sonnet-5"

    # Neither: no variable, and a current directory without hotdocs.toml.
    monkeypatch.delenv(ENV_NAME, raising=False)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    assert llm_endpoint.load_config() is None


def test_named_file_missing_raises_value_error(clean_env, monkeypatch, tmp_path):
    # Even with a valid hotdocs.toml in the cwd, a named missing file is an error.
    _write(
        clean_env / "hotdocs.toml",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\n',
    )
    missing = tmp_path / "does-not-exist" / "hotdocs.toml"
    monkeypatch.setenv(ENV_NAME, str(missing))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


# ---------------------------------------------------------------------------
# Scenario 2: invalid [llm] tables
# ---------------------------------------------------------------------------


INVALID_CASES = [
    (
        "unknown_entry",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\nflavour = "vanilla"\n',
        ["flavour"],
    ),
    (
        "provider_outside_list",
        '[llm]\nprovider = "not-a-provider"\nmodel = "gpt-6-astra"\n',
        ["provider"],
    ),
    (
        "no_model",
        '[llm]\nprovider = "openai"\n',
        ["model"],
    ),
    (
        "timeout_120",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\ntimeout_seconds = 120\n',
        ["timeout"],
    ),
    (
        "claude_cli_with_base_url",
        '[llm]\nprovider = "claude-cli"\nmodel = "claude-sonnet-5"\n'
        'base_url = "https://example.invalid"\n',
        ["base_url"],
    ),
]


@pytest.mark.parametrize(
    "name,text,needles", INVALID_CASES, ids=[c[0] for c in INVALID_CASES]
)
def test_invalid_table_raises_value_error_naming_problem(
    clean_env, tmp_path, name, text, needles
):
    path = _write(tmp_path / "cases" / name / "hotdocs.toml", text)
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config(path)
    message = str(excinfo.value).lower()
    for needle in needles:
        assert needle.lower() in message, (name, str(excinfo.value))


def test_api_key_entry_rejected_as_secret(clean_env, tmp_path):
    path = _write(
        tmp_path / "cases" / "api_key" / "hotdocs.toml",
        '[llm]\nprovider = "openai"\nmodel = "gpt-6-astra"\n'
        'api_key = "sk-not-a-real-key-0123456789"\n',
    )
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config(path)
    message = str(excinfo.value)
    assert "must never hold a secret" in message
    assert "hotdocs.toml" in message


# ---------------------------------------------------------------------------
# Scenario 3: save_config replaces only [llm]
# ---------------------------------------------------------------------------


@pytest.mark.skipif(tomllib is None, reason="tomllib requires Python 3.11+")
def test_save_config_replaces_llm_and_keeps_other(clean_env, monkeypatch, tmp_path):
    secret = "sk-ant-secret-value-do-not-write-7f3a9c"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)

    path = _write(
        tmp_path / "proj" / "hotdocs.toml",
        '[llm]\n'
        'provider = "openai"\n'
        'model = "gpt-6-astra"\n'
        '\n'
        '[other]\n'
        'name = "keep"\n'
        'count = 3\n'
        'items = ["a", "b"]\n',
    )
    original_other = tomllib.loads(path.read_text(encoding="utf-8"))["other"]

    llm_endpoint.save_config(
        path,
        "anthropic",
        "claude-sonnet-5",
        api_key_env="ANTHROPIC_API_KEY",
    )

    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)

    llm = data["llm"]
    assert llm["provider"] == "anthropic"
    assert llm["model"] == "claude-sonnet-5"
    assert llm.get("api_key_env") == "ANTHROPIC_API_KEY"

    assert data["other"] == original_other

    # Never a secret: neither the key's value nor a secret-named entry.
    assert secret not in text
    secretish = ("api_key", "token", "password", "secret")
    for key in llm:
        if key == "api_key_env":
            continue
        assert not any(s in key.lower() for s in secretish), key
    for value in os.environ.values():
        if value and len(value) >= 20 and value.startswith("sk-"):
            assert value not in text