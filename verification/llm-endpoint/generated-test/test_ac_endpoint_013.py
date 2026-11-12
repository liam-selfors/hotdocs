import os
import stat

import pytest

import llm_endpoint


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


@pytest.fixture
def fresh_cwd(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return work


def test_missing_file_named_by_var_raises_value_error(fresh_cwd, tmp_path, monkeypatch):
    missing = tmp_path / "does-not-exist" / "hotdocs.toml"
    assert not missing.exists()
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(missing))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


def test_non_toml_file_named_by_var_raises_value_error(fresh_cwd, tmp_path, monkeypatch):
    bad = tmp_path / "not_toml.toml"
    bad.write_text("{{{ this is :: not = = toml [[[\n", encoding="utf-8")
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(bad))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


def test_toml_with_only_other_table_returns_none(fresh_cwd, tmp_path, monkeypatch):
    other = tmp_path / "other.toml"
    other.write_text('[other]\nname = "value"\ncount = 3\n', encoding="utf-8")
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(other))
    assert llm_endpoint.load_config() is None
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    assert llm_endpoint.load_config(other) is None


def test_save_config_creates_directory_and_round_trips(fresh_cwd, tmp_path):
    sub = tmp_path / "cfgdir" / "sub"
    assert not sub.exists()
    path = sub / "hotdocs.toml"

    llm_endpoint.save_config(path, "openai", "gpt-6-astra", timeout_seconds=900)

    assert sub.is_dir()
    assert path.is_file()

    cfg = llm_endpoint.load_config(path)
    assert cfg is not None
    assert _get(cfg, "provider") == "openai"
    assert _get(cfg, "model") == "gpt-6-astra"
    assert _get(cfg, "timeout_seconds") == 900
    assert _get(cfg, "base_url") is None
    assert _get(cfg, "api_key_env") is None

    llm_endpoint.save_config(path, "ollama", "llama3.2")

    cfg2 = llm_endpoint.load_config(path)
    assert cfg2 is not None
    assert _get(cfg2, "provider") == "ollama"
    assert _get(cfg2, "model") == "llama3.2"
    assert _get(cfg2, "timeout_seconds") is None


def test_detect_providers_with_given_env(fresh_cwd, tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert os.access(str(claude), os.X_OK)

    env = {"PATH": str(bindir), "OPENAI_API_KEY": "k"}
    result = llm_endpoint.detect_providers(env=env, probe_ollama=False)

    by_name = {}
    for entry in result:
        by_name[_get(entry, "provider")] = entry

    for name in ("claude-cli", "openai", "anthropic", "gemini", "ollama"):
        assert name in by_name, f"missing provider entry {name!r} in {result!r}"

    assert _get(by_name["claude-cli"], "available") is True
    assert _get(by_name["openai"], "available") is True
    assert not _get(by_name["anthropic"], "available")
    assert not _get(by_name["gemini"], "available")
    assert not _get(by_name["ollama"], "available")

    assert _get(by_name["openai"], "api_key_env") == "OPENAI_API_KEY"