# hotdocs-criterion: sha256:edecc5653ecc60cfcd8720df6354d5d983ac5dfa5d86ac9f03adb133e922b664
import importlib.metadata
import os
import stat
import subprocess
import sys

import hotdocs_init


FAKE_ENDPOINT_BODY = '''
import json
import os
import tomllib


def _log(name, **kwargs):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"call": name, "args": {k: repr(v) for k, v in kwargs.items()}}) + "\\n")


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
    _log("detect_providers", env=env, probe_ollama=probe_ollama)
    result = []
    for name, info in PROVIDERS.items():
        available = name == "ollama"
        result.append({
            "provider": name,
            "available": available,
            "reason": "fake: available" if available else "fake: not available",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return result


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30, auth=None):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def _strip_llm(text):
    out = []
    skipping = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            skipping = stripped == "[llm]"
        if not skipping:
            out.append(line)
    return "\\n".join(out).strip()


def save_config(config_path, provider, model, base_url=None, api_key_env=None,
                timeout_seconds=None, auth=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds, auth=auth)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    path = str(config_path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    existing = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            existing = handle.read()
    kept = _strip_llm(existing)
    lines = ["[llm]", "provider = " + json.dumps(provider), "model = " + json.dumps(model)]
    if base_url is not None:
        lines.append("base_url = " + json.dumps(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + json.dumps(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(int(timeout_seconds)))
    if auth is not None:
        lines.append("auth = " + json.dumps(auth))
    text = (kept + "\\n\\n" if kept else "") + "\\n".join(lines) + "\\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path) if config_path is not None else None)
    path = str(config_path) if config_path is not None else "hotdocs.toml"
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        try:
            data = tomllib.load(handle)
        except Exception as exc:
            raise ValueError("invalid config") from exc
    llm = data.get("llm")
    if llm is None:
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


def make_tool_root(tmp_path, requirement_lines):
    tool_root = tmp_path / "tool"
    log_path = tmp_path / "logs" / "calls.log"
    ep_dir = tool_root / "gen" / "llm-endpoint"
    ep_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_ENDPOINT_BODY
    (ep_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")
    ex = tool_root / "examples" / "slugify" / "specs" / "product"
    ex.mkdir(parents=True)
    (ex / "slugs.md").write_text("# Slugs\n\nExample product spec.\n", encoding="utf-8")
    (tool_root / "requirements.txt").write_text(
        "\n".join(requirement_lines) + "\n", encoding="utf-8"
    )
    return tool_root


def installed_pytest_line():
    return "pytest==" + importlib.metadata.version("pytest")


def flatten(messages):
    lines = []
    for msg in messages:
        lines.extend(str(msg).split("\n"))
    return lines


def install_command_guard(monkeypatch):
    commands = []

    def fake_popen(*args, **kwargs):
        commands.append(("Popen", args))
        raise OSError("command execution forbidden in test")

    def fake_system(*args, **kwargs):
        commands.append(("system", args))
        return 1

    def fake_os_popen(*args, **kwargs):
        commands.append(("os.popen", args))
        raise OSError("command execution forbidden in test")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(os, "system", fake_system)
    monkeypatch.setattr(os, "popen", fake_os_popen)
    return commands


def run_init(tmp_path, monkeypatch, requirement_lines, provider, model, claude_on_path):
    tool_root = make_tool_root(tmp_path, requirement_lines)
    project = tmp_path / "proj"
    project.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    if claude_on_path:
        claude = bin_dir / "claude"
        claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    env = {"PATH": str(bin_dir), "HOME": str(tmp_path / "home")}

    outputs = []
    prompts = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        prompts.append(prompt)
        if len(prompts) > 50:
            raise RuntimeError("too many prompts")
        return ""

    commands = install_command_guard(monkeypatch)
    argv = [
        str(project),
        "--provider", provider,
        "--model", model,
        "--no-test",
        "--yes",
    ]
    code = hotdocs_init.run(
        argv,
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=str(project),
    )
    return code, flatten(outputs), commands, tool_root, project


def has_consecutive(lines, first, second):
    for i in range(len(lines) - 1):
        if lines[i] == first and lines[i + 1] == second:
            return True
    return False


def test_missing_requirement_reported_returns_3(tmp_path, monkeypatch, capsys):
    code, lines, commands, tool_root, project = run_init(
        tmp_path,
        monkeypatch,
        ["pytest==9.2.0", "no-such-pkg-xyz==1.0"],
        "ollama",
        "llama3.2",
        claude_on_path=False,
    )
    assert code == 3
    # Skeleton was created
    assert project.is_dir()
    assert any(project.iterdir())
    # No example copied
    assert not (project / "specs" / "product" / "slugs.md").exists()
    assert not (project / "examples").exists()
    fix = "  fix: pip install -r " + str(tool_root) + "/requirements.txt"
    assert has_consecutive(lines, "missing: no-such-pkg-xyz==1.0", fix), lines
    # pytest is installed, so it is not reported missing despite a version mismatch
    assert "missing: pytest==9.2.0" not in lines
    assert commands == []
    err = capsys.readouterr().err
    assert "missing:" not in err


def test_claude_cli_without_claude_on_path_returns_3(tmp_path, monkeypatch, capsys):
    code, lines, commands, tool_root, project = run_init(
        tmp_path,
        monkeypatch,
        [installed_pytest_line()],
        "claude-cli",
        "claude-sonnet-5",
        claude_on_path=False,
    )
    assert code == 3
    assert has_consecutive(
        lines, "missing: claude on PATH", "  fix: install Claude Code and sign in"
    ), lines
    assert commands == []
    err = capsys.readouterr().err
    assert "missing:" not in err


def test_claude_cli_with_claude_on_path_returns_0(tmp_path, monkeypatch):
    code, lines, commands, tool_root, project = run_init(
        tmp_path,
        monkeypatch,
        [installed_pytest_line()],
        "claude-cli",
        "claude-sonnet-5",
        claude_on_path=True,
    )
    assert code == 0, lines
    assert "missing: claude on PATH" not in lines
    assert commands == []


def test_ollama_without_claude_on_path_returns_0(tmp_path, monkeypatch):
    code, lines, commands, tool_root, project = run_init(
        tmp_path,
        monkeypatch,
        [installed_pytest_line()],
        "ollama",
        "llama3.2",
        claude_on_path=False,
    )
    assert code == 0, lines
    assert "missing: claude on PATH" not in lines
    assert commands == []