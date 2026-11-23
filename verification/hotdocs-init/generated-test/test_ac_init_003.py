# hotdocs-criterion: sha256:e94ac1372ac455802ace49c738f33c65e1dfc405a678ce559ac83204bbf8ab1a
import os
import stat
import subprocess
from pathlib import Path

import hotdocs_init


FAKE_ENDPOINT_BODY = '''
import json
import tomllib
from pathlib import Path

PROVIDERS = {
    "claude-cli": {"default_base_url": None, "default_api_key_env": None,
                   "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "anthropic": {"default_base_url": "https://api.anthropic.com",
                  "default_api_key_env": "ANTHROPIC_API_KEY",
                  "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "openai": {"default_base_url": "https://api.openai.com/v1",
               "default_api_key_env": "OPENAI_API_KEY",
               "needs_base_url": False, "suggested_model": "gpt-6-astra"},
    "openai-compatible": {"default_base_url": None, "default_api_key_env": None,
                          "needs_base_url": True, "suggested_model": ""},
    "gemini": {"default_base_url": "https://generativelanguage.googleapis.com",
               "default_api_key_env": "GEMINI_API_KEY",
               "needs_base_url": False, "suggested_model": "gemini-4-argon"},
    "ollama": {"default_base_url": "http://localhost:11434",
               "default_api_key_env": None,
               "needs_base_url": False, "suggested_model": "llama3.2"},
}


def _log(line):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers")
    out = []
    for name, info in PROVIDERS.items():
        out.append({
            "provider": name,
            "available": name in ("claude-cli", "ollama"),
            "reason": "fake",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection " + str(provider))
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None,
                api_key_env=None, timeout_seconds=None, auth=None):
    _log("save_config " + str(provider))
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[llm]", "provider = " + json.dumps(provider),
             "model = " + json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + json.dumps(auth))
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config")
    if config_path is None:
        return None
    path = Path(config_path)
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("invalid config")
    llm = data.get("llm")
    if not isinstance(llm, dict):
        return None
    return {
        "provider": llm.get("provider"),
        "model": llm.get("model"),
        "base_url": llm.get("base_url"),
        "api_key_env": llm.get("api_key_env"),
        "timeout_seconds": llm.get("timeout_seconds"),
        "auth": llm.get("auth"),
    }
'''


def make_tool_root(tmp_path, requirements_lines):
    tool_root = tmp_path / "tool"
    endpoint_dir = tool_root / "gen" / "llm-endpoint"
    endpoint_dir.mkdir(parents=True)
    log_path = tmp_path / "logs" / "endpoint.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_ENDPOINT_BODY
    (endpoint_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")
    slugs = tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md"
    slugs.parent.mkdir(parents=True)
    slugs.write_text("# Slugs\n\nAn example product spec.\n", encoding="utf-8")
    (tool_root / "requirements.txt").write_text(
        "\n".join(requirements_lines) + "\n", encoding="utf-8"
    )
    (tool_root / "pyproject.toml").write_text(
        '[project]\nname = "hotdocs"\nversion = "9.8.7a1"\n', encoding="utf-8"
    )
    return tool_root


def installed_requirements():
    import importlib.metadata
    return ["pytest==" + importlib.metadata.version("pytest")]


def block_commands(monkeypatch):
    calls = []

    def fake_popen(*args, **kwargs):
        calls.append(("Popen", args))
        raise AssertionError("a command was run: " + repr(args))

    def fake_system(*args, **kwargs):
        calls.append(("system", args))
        raise AssertionError("a command was run: " + repr(args))

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(os, "system", fake_system)
    return calls


def run_init(tmp_path, tool_root, provider, path_dir, name):
    project = tmp_path / name
    project.mkdir()
    out = []
    asked = []

    def output_fn(*args, **kwargs):
        out.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        asked.append(prompt)
        if len(asked) > 50:
            raise AssertionError("too many questions")
        return ""

    env = {"PATH": str(path_dir)}
    model = "claude-sonnet-5" if provider == "claude-cli" else "llama3.2"
    argv = [str(project), "--provider", provider, "--model", model,
            "--no-test", "--yes"]
    code = hotdocs_init.run(
        argv,
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=str(project),
    )
    lines = "\n".join(out).splitlines()
    return code, lines, project


def empty_bin(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d


def test_missing_requirement_reported_and_returns_3(tmp_path, monkeypatch, capsys):
    tool_root = make_tool_root(tmp_path, ["pytest==9.2.0", "no-such-pkg-xyz==1.0"])
    calls = block_commands(monkeypatch)
    bindir = empty_bin(tmp_path, "bin_empty")
    code, lines, project = run_init(tmp_path, tool_root, "ollama", bindir, "proj1")

    assert code == 3
    # skeleton was created
    assert any(project.iterdir())
    assert "missing: no-such-pkg-xyz==1.0" in lines
    i = lines.index("missing: no-such-pkg-xyz==1.0")
    expected_fix = "  fix: pip install -r " + str(tool_root) + "/requirements.txt"
    assert lines[i + 1] == expected_fix
    assert "missing: pytest==9.2.0" not in lines
    assert calls == []
    assert "missing:" not in capsys.readouterr().err


def test_claude_missing_on_path_returns_3(tmp_path, monkeypatch, capsys):
    tool_root = make_tool_root(tmp_path, installed_requirements())
    calls = block_commands(monkeypatch)
    bindir = empty_bin(tmp_path, "bin_empty")
    code, lines, project = run_init(tmp_path, tool_root, "claude-cli", bindir, "proj2")

    assert code == 3
    assert "missing: claude on PATH" in lines
    i = lines.index("missing: claude on PATH")
    assert lines[i + 1] == "  fix: install Claude Code and sign in"
    assert calls == []
    assert "missing:" not in capsys.readouterr().err


def test_claude_present_on_path_returns_0(tmp_path, monkeypatch):
    tool_root = make_tool_root(tmp_path, installed_requirements())
    calls = block_commands(monkeypatch)
    bindir = empty_bin(tmp_path, "bin_claude")
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    code, lines, project = run_init(tmp_path, tool_root, "claude-cli", bindir, "proj3")

    assert code == 0
    assert "missing: claude on PATH" not in lines
    assert calls == []


def test_ollama_without_claude_returns_0(tmp_path, monkeypatch):
    tool_root = make_tool_root(tmp_path, installed_requirements())
    calls = block_commands(monkeypatch)
    bindir = empty_bin(tmp_path, "bin_empty")
    code, lines, project = run_init(tmp_path, tool_root, "ollama", bindir, "proj4")

    assert code == 0
    assert "missing: claude on PATH" not in lines
    assert calls == []