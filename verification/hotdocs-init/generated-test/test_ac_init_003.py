# hotdocs-criterion: sha256:7c5a3770cafe8e46759708d8069b74e64f86e3fc798078e314b1015fd3435523
import importlib.metadata
import os
import stat
import subprocess
from pathlib import Path

import pytest

import hotdocs_init


FAKE_LLM_ENDPOINT_BODY = r'''
import json
import shutil
import tomllib
from pathlib import Path


def _log(name, **kwargs):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": kwargs}, default=str) + "\n")


PROVIDERS = {
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "anthropic": {
        "default_base_url": "https://api.anthropic.com",
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "openai": {
        "default_base_url": "https://api.openai.com/v1",
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-6-astra",
    },
    "openai-compatible": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    },
    "gemini": {
        "default_base_url": "https://generativelanguage.googleapis.com",
        "default_api_key_env": "GEMINI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gemini-4-argon",
    },
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.2",
    },
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    env = env if env is not None else {}
    out = []
    for name, info in PROVIDERS.items():
        if name == "claude-cli":
            available = shutil.which("claude", path=env.get("PATH")) is not None
            reason = "claude found on PATH" if available else "claude not on PATH"
        elif name == "ollama":
            available = True
            reason = "fake ollama"
        else:
            key = info["default_api_key_env"]
            available = bool(key and env.get(key))
            reason = "key set" if available else "no key"
        out.append({
            "provider": name,
            "available": available,
            "reason": reason,
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not isinstance(model, str) or not model:
        raise ValueError("model required")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.exists():
        in_llm = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_llm = stripped == "[llm]"
            if not in_llm:
                kept.append(line)
    lines = list(kept)
    lines.append("[llm]")
    lines.append("provider = " + json.dumps(provider))
    lines.append("model = " + json.dumps(model))
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + json.dumps(auth))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    path = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("invalid config") from exc
    llm = data.get("llm")
    if llm is None:
        return None
    if not isinstance(llm, dict):
        raise ValueError("invalid [llm]")
    return {
        "provider": llm.get("provider"),
        "model": llm.get("model"),
        "base_url": llm.get("base_url"),
        "api_key_env": llm.get("api_key_env"),
        "timeout_seconds": llm.get("timeout_seconds"),
        "auth": llm.get("auth"),
    }
'''


def make_tool_root(base, requirements_lines, log_path):
    tool_root = base / "toolroot"
    ep = tool_root / "gen" / "llm-endpoint"
    ep.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY
    (ep / "llm_endpoint.py").write_text(source, encoding="utf-8")
    slugs = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nA fake example product spec.\n", encoding="utf-8")
    (tool_root / "requirements.txt").write_text(
        "\n".join(requirements_lines) + "\n", encoding="utf-8"
    )
    (tool_root / "pyproject.toml").write_text(
        '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n', encoding="utf-8"
    )
    return tool_root


def installed_pytest_line():
    return "pytest==" + importlib.metadata.version("pytest")


@pytest.fixture
def commands(monkeypatch):
    ran = []

    def recorder(name):
        def _fake(*args, **kwargs):
            ran.append((name, args))
            raise AssertionError("init ran a command via " + name)
        return _fake

    for name in ("run", "Popen", "call", "check_call", "check_output", "getoutput",
                 "getstatusoutput"):
        if hasattr(subprocess, name):
            monkeypatch.setattr(subprocess, name, recorder("subprocess." + name))
    for name in ("system", "popen", "execv", "execve", "execvp", "execvpe",
                 "spawnv", "spawnve", "spawnvp", "spawnvpe", "posix_spawn",
                 "posix_spawnp"):
        if hasattr(os, name):
            monkeypatch.setattr(os, name, recorder("os." + name))
    return ran


def run_init(tmp_path, tool_root, name, provider, model, path_dir):
    project = tmp_path / name
    project.mkdir()
    home = tmp_path / ("home-" + name)
    home.mkdir()
    env = {"PATH": str(path_dir), "HOME": str(home)}
    out_lines = []

    def output_fn(*args, **kwargs):
        text = " ".join(str(a) for a in args)
        out_lines.extend(text.splitlines() if text else [""])

    asked = []

    def input_fn(prompt=""):
        asked.append(prompt)
        if len(asked) > 50:
            raise AssertionError("too many questions")
        return ""

    argv = [str(project), "--provider", provider, "--model", model, "--no-test", "--yes"]
    code = hotdocs_init.run(
        argv,
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=str(project),
    )
    return code, out_lines, project


def has_consecutive(lines, first, second):
    return any(lines[i] == first and lines[i + 1] == second for i in range(len(lines) - 1))


def test_missing_requirement_reported_returns_3_without_running_commands(tmp_path, commands, capsys):
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    tool_root = make_tool_root(tmp_path, ["pytest==9.2.0", "no-such-pkg-xyz==1.0"], log_path)
    path_dir = tmp_path / "emptybin"
    path_dir.mkdir()

    code, lines, project = run_init(tmp_path, tool_root, "proj", "ollama", "llama3.2", path_dir)

    assert code == 3, lines
    # skeleton was created
    assert any(project.iterdir()), "init created no skeleton"
    # no example involved
    assert not list(project.rglob("slugs.md"))
    assert "missing: no-such-pkg-xyz==1.0" in lines
    fix = "  fix: pip install -r " + str(tool_root) + "/requirements.txt"
    assert has_consecutive(lines, "missing: no-such-pkg-xyz==1.0", fix), lines
    # pytest is installed (version mismatch does not count as missing)
    assert not any(line.startswith("missing: pytest") for line in lines)
    assert "missing: claude on PATH" not in lines
    assert commands == []
    err = capsys.readouterr().err
    assert "missing:" not in err


def test_claude_cli_missing_from_path_returns_3(tmp_path, commands, capsys):
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    tool_root = make_tool_root(tmp_path, [installed_pytest_line()], log_path)
    path_dir = tmp_path / "emptybin"
    path_dir.mkdir()

    code, lines, project = run_init(
        tmp_path, tool_root, "proj", "claude-cli", "claude-sonnet-5", path_dir
    )

    assert code == 3, lines
    assert has_consecutive(
        lines, "missing: claude on PATH", "  fix: install Claude Code and sign in"
    ), lines
    assert not any(line.startswith("missing: pytest") for line in lines)
    assert commands == []
    assert "missing:" not in capsys.readouterr().err


def test_claude_cli_present_on_path_returns_0(tmp_path, commands):
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    tool_root = make_tool_root(tmp_path, [installed_pytest_line()], log_path)
    path_dir = tmp_path / "bin"
    path_dir.mkdir()
    claude = path_dir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    code, lines, project = run_init(
        tmp_path, tool_root, "proj", "claude-cli", "claude-sonnet-5", path_dir
    )

    assert code == 0, lines
    assert not any(line.startswith("missing:") for line in lines)
    assert commands == []


def test_ollama_without_claude_on_path_returns_0(tmp_path, commands):
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    tool_root = make_tool_root(tmp_path, [installed_pytest_line()], log_path)
    path_dir = tmp_path / "emptybin"
    path_dir.mkdir()

    code, lines, project = run_init(tmp_path, tool_root, "proj", "ollama", "llama3.2", path_dir)

    assert code == 0, lines
    assert "missing: claude on PATH" not in lines
    assert not any(line.startswith("missing:") for line in lines)
    assert commands == []