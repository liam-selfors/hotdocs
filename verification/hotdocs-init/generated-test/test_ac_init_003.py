# hotdocs-criterion: sha256:73de4bca974ee2178f56989515571c4b7670a87aa85797ccabe9f7d88a9c7f66
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

import pytest

import hotdocs_init


FAKE_LLM_ENDPOINT_BODY = '''
import json
import shutil
from pathlib import Path


def _log(name, payload):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": name, "args": payload}, default=str) + "\\n")


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
    _log("detect_providers", {"env_given": env is not None, "probe_ollama": probe_ollama})
    path = None if env is None else env.get("PATH")
    out = []
    for name, info in PROVIDERS.items():
        if name == "claude-cli":
            found = shutil.which("claude", path=path) is not None
            available = found
            reason = "claude on PATH" if found else "claude not on PATH"
        elif name == "ollama":
            available = True
            reason = "ollama reachable"
        else:
            available = False
            reason = "not configured"
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
    _log("check_connection", {"provider": provider, "model": model})
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


_KEYS = ("provider", "model", "base_url", "api_key_env", "timeout_seconds", "auth")


def save_config(config_path, provider, model, base_url=None,
                api_key_env=None, timeout_seconds=None, auth=None):
    _log("save_config", {"config_path": str(config_path), "provider": provider, "model": model})
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not model and provider != "openai-compatible":
        raise ValueError("model required")
    p = Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if p.is_file():
        in_llm = False
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                in_llm = (s == "[llm]")
                if in_llm:
                    continue
            if not in_llm:
                kept.append(line)
    values = {
        "provider": provider, "model": model, "base_url": base_url,
        "api_key_env": api_key_env, "timeout_seconds": timeout_seconds, "auth": auth,
    }
    lines = list(kept)
    if lines and lines[-1].strip():
        lines.append("")
    lines.append("[llm]")
    for k in _KEYS:
        v = values[k]
        if v is None:
            continue
        lines.append(k + " = " + json.dumps(v))
    p.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", {"config_path": str(config_path)})
    if config_path is None:
        config_path = Path("hotdocs.toml")
    p = Path(config_path)
    if not p.is_file():
        return None
    found = False
    in_llm = False
    result = {k: None for k in _KEYS}
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_llm = (s == "[llm]")
            if in_llm:
                found = True
            continue
        if in_llm and "=" in s:
            k, v = s.split("=", 1)
            k = k.strip()
            if k in result:
                try:
                    result[k] = json.loads(v.strip())
                except Exception:
                    raise ValueError("invalid value")
    if not found:
        return None
    return result
'''


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_tool_root(base, requirement_lines):
    tool_root = base / "tool"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_endpoint_calls.log"

    ep_dir = tool_root / "gen" / "llm-endpoint"
    ep_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_LLM_ENDPOINT_BODY
    (ep_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    ex_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    ex_dir.mkdir(parents=True)
    (ex_dir / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")

    (tool_root / "requirements.txt").write_text(
        "\n".join(requirement_lines) + "\n", encoding="utf-8"
    )
    return tool_root, log_path


def installed_requirements():
    return ["pytest==" + importlib.metadata.version("pytest")]


@pytest.fixture
def no_commands(monkeypatch):
    calls = []

    def make_recorder(name):
        def recorder(*args, **kwargs):
            calls.append((name, args, kwargs))
            raise RuntimeError("command execution forbidden in test: " + name)
        return recorder

    for name in ("run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"):
        monkeypatch.setattr(subprocess, name, make_recorder("subprocess." + name))
    monkeypatch.setattr(os, "system", make_recorder("os.system"))
    monkeypatch.setattr(os, "popen", make_recorder("os.popen"))
    return calls


def make_io():
    outputs = []
    prompts = []

    def output_fn(*args, **kwargs):
        sep = kwargs.get("sep", " ")
        outputs.append(sep.join(str(a) for a in args))

    def input_fn(prompt=""):
        prompts.append(prompt)
        if len(prompts) > 50:
            raise RuntimeError("too many prompts")
        return ""

    return outputs, prompts, output_fn, input_fn


def output_lines(outputs):
    lines = []
    for chunk in outputs:
        lines.extend(chunk.split("\n"))
    return lines


def has_consecutive(lines, first, second):
    for i in range(len(lines) - 1):
        if lines[i] == first and lines[i + 1] == second:
            return True
    return False


def run_init(tmp_path, tool_root, project_name, provider, model, path_dir):
    project = tmp_path / project_name
    project.mkdir()
    outputs, prompts, output_fn, input_fn = make_io()
    env = {"PATH": str(path_dir)}
    argv = [
        str(project),
        "--provider", provider,
        "--model", model,
        "--no-test",
        "--yes",
    ]
    rc = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env=env,
        cwd=str(tmp_path),
    )
    return rc, project, output_lines(outputs)


def test_missing_requirement_reported_and_returns_3(tmp_path, no_commands, capsys):
    tool_root, _log = make_tool_root(
        tmp_path, ["pytest==9.2.0", "no-such-pkg-xyz==1.0"]
    )
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()

    rc, project, lines = run_init(
        tmp_path, tool_root, "proj1", "ollama", "llama3.2", empty_bin
    )

    assert rc == 3
    # The skeleton was created despite the missing prerequisite.
    assert any(project.iterdir())
    # No example involved.
    assert not (project / "examples").exists()

    expected_fix = "  fix: pip install -r " + str(tool_root) + "/requirements.txt"
    assert has_consecutive(lines, "missing: no-such-pkg-xyz==1.0", expected_fix), lines
    # pytest is installed: its line is never reported missing, whatever its version.
    assert "missing: pytest==9.2.0" not in lines

    assert no_commands == []
    err = capsys.readouterr().err
    assert "missing:" not in err


def test_claude_cli_without_claude_on_path_returns_3(tmp_path, no_commands, capsys):
    tool_root, _log = make_tool_root(tmp_path, installed_requirements())
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()

    rc, project, lines = run_init(
        tmp_path, tool_root, "proj2", "claude-cli", "claude-sonnet-5", empty_bin
    )

    assert rc == 3
    assert has_consecutive(
        lines, "missing: claude on PATH", "  fix: install Claude Code and sign in"
    ), lines
    assert no_commands == []
    err = capsys.readouterr().err
    assert "missing:" not in err


def test_claude_cli_with_claude_on_path_returns_0(tmp_path, no_commands):
    tool_root, _log = make_tool_root(tmp_path, installed_requirements())
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    claude = bin_dir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(0o755)

    rc, project, lines = run_init(
        tmp_path, tool_root, "proj3", "claude-cli", "claude-sonnet-5", bin_dir
    )

    assert rc == 0, lines
    assert "missing: claude on PATH" not in lines
    assert no_commands == []


def test_ollama_without_claude_on_path_returns_0(tmp_path, no_commands):
    tool_root, _log = make_tool_root(tmp_path, installed_requirements())
    empty_bin = tmp_path / "emptybin"
    empty_bin.mkdir()

    rc, project, lines = run_init(
        tmp_path, tool_root, "proj4", "ollama", "llama3.2", empty_bin
    )

    assert rc == 0, lines
    assert "missing: claude on PATH" not in lines
    assert no_commands == []