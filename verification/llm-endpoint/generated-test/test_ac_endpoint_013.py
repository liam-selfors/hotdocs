# hotdocs-criterion: sha256:a2aff241b318609daa4b7b8395449e20b7550ab8258d8d7b69e742b2f5909ab6
import os
import stat
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return tmp_path


def test_load_config_missing_file_raises_value_error(isolated, monkeypatch):
    missing = isolated / "does-not-exist" / "hotdocs.toml"
    assert not missing.exists()
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(missing))
    with pytest.raises(ValueError):
        llm_endpoint.load_config()


def test_load_config_not_toml_raises_value_error(isolated, monkeypatch):
    bad = isolated / "bad.toml"
    bad.write_text("this is [[[ not = = valid toml\n\x00 ][\n", encoding="utf-8")
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(bad))
    with pytest.raises(ValueError) as excinfo:
        llm_endpoint.load_config()
    assert "not valid TOML" in str(excinfo.value)


def test_load_config_only_other_table_returns_none(isolated, monkeypatch):
    other = isolated / "other.toml"
    other.write_text('[other]\nkey = "value"\n', encoding="utf-8")
    monkeypatch.setenv("VAR_HOTDOCS_CONFIG", str(other))
    assert llm_endpoint.load_config() is None


def test_save_config_creates_directory_and_round_trips(isolated):
    sub = isolated / "dir" / "sub"
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
    assert field(cfg2, "model") == "llama3.2"
    assert field(cfg2, "timeout_seconds") is None


def test_detect_providers_with_env(isolated, monkeypatch):
    def no_network(*args, **kwargs):
        raise urllib.error.URLError("network disabled in test")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)

    bindir = isolated / "bin"
    bindir.mkdir()
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    env = {"PATH": str(bindir), "OPENAI_API_KEY": "k"}
    result = llm_endpoint.detect_providers(env=env, probe_ollama=False)

    by_name = {}
    for entry in result:
        by_name[field(entry, "provider")] = entry

    for name in ("claude-cli", "openai", "anthropic", "gemini", "ollama"):
        assert name in by_name, name

    assert bool(field(by_name["claude-cli"], "available")) is True
    assert bool(field(by_name["openai"], "available")) is True
    assert bool(field(by_name["anthropic"], "available")) is False
    assert bool(field(by_name["gemini"], "available")) is False
    assert bool(field(by_name["ollama"], "available")) is False

    assert field(by_name["openai"], "api_key_env") == "OPENAI_API_KEY"