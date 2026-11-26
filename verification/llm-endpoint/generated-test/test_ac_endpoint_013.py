# hotdocs-criterion: sha256:b6e5ee21a8bea67c3d9deb3eb3304be9e97a1c5e2379708cb43bdfdd88b7544e
import os
import stat
from pathlib import Path

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return tmp_path


def test_load_config_missing_file_raises(clean_env, monkeypatch):
    missing = clean_env / "does-not-exist.toml"
    assert not missing.exists()
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(missing))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


def test_load_config_not_toml_raises(clean_env, monkeypatch):
    bad = clean_env / "bad.toml"
    bad.write_text("this is [[[ not = = valid toml\n\x00 ]]\n", encoding="utf-8")
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(bad))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


def test_load_config_only_other_table_returns_none(clean_env, monkeypatch):
    other = clean_env / "other.toml"
    other.write_text('[other]\nkey = "value"\n', encoding="utf-8")
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(other))
    assert llm_endpoint.load_config() is None


def test_save_config_creates_directory_and_round_trips(clean_env):
    sub = clean_env / "cfgdir" / "sub"
    assert not sub.exists()
    path = sub / "hotdocs.toml"

    llm_endpoint.save_config(path, "openai", "gpt-6-astra", timeout_seconds=900)

    assert sub.is_dir()
    assert path.is_file()

    cfg = llm_endpoint.load_config(path)
    assert cfg is not None
    assert field(cfg, "provider") == "openai"
    assert field(cfg, "model") == "gpt-6-astra"
    assert field(cfg, "timeout_seconds") == 900
    assert field(cfg, "base_url") is None
    assert field(cfg, "api_key_env") is None

    llm_endpoint.save_config(path, "ollama", "llama3.2")

    cfg2 = llm_endpoint.load_config(path)
    assert cfg2 is not None
    assert field(cfg2, "provider") == "ollama"
    assert field(cfg2, "timeout_seconds") is None


def test_detect_providers_from_env(clean_env):
    bindir = clean_env / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    env = {"PATH": str(bindir), "OPENAI_API_KEY": "k"}
    result = llm_endpoint.detect_providers(env=env, probe_ollama=False)

    by_name = {field(entry, "provider"): entry for entry in result}

    for name in ("claude-cli", "openai", "anthropic", "gemini", "ollama"):
        assert name in by_name, name

    assert field(by_name["claude-cli"], "available") is True
    assert field(by_name["openai"], "available") is True
    assert field(by_name["anthropic"], "available") is False
    assert field(by_name["gemini"], "available") is False
    assert field(by_name["ollama"], "available") is False

    assert field(by_name["openai"], "api_key_env") == "OPENAI_API_KEY"