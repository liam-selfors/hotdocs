import importlib.metadata
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import hotdocs_init


pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="the Python 3.11+ prerequisite would itself be reported missing",
)


FAKE_LLM_ENDPOINT = r'''
import json
import os
import shutil
from pathlib import Path

LOG_PATH = __LOG_PATH__

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


def _log(name, **kwargs):
    p = Path(LOG_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"name": name, "args": kwargs}, default=str) + "\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    source = os.environ if env is None else env
    out = []
    for name, info in PROVIDERS.items():
        key_env = info["default_api_key_env"]
        if name == "claude-cli":
            available = shutil.which("claude", path=source.get("PATH")) is not None
            reason = "claude found on PATH" if available else "claude not found on PATH"
        elif name == "ollama":
            available = bool(probe_ollama)
            reason = "fake probe" if available else "not probed"
        elif name == "openai-compatible":
            available = False
            reason = "needs a base URL"
        else:
            available = bool(source.get(key_env))
            reason = ("%s is set" % key_env) if available else ("%s is not set" % key_env)
        out.append({
            "provider": name,
            "available": available,
            "reason": reason,
            "suggested_model": info["suggested_model"],
            "api_key_env": key_env,
        })
    return out


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env, timeout_seconds=timeout_seconds)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url is required for %s" % provider)
    return {"ok": True, "error": None}


def _q(value):
    return json.dumps(value)


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config", config_path=str(config_path), provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env, timeout_seconds=timeout_seconds)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)
    if not isinstance(model, str) or not model:
        raise ValueError("model must be a non-empty string")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url is required for %s" % provider)
    if api_key_env is not None and (not isinstance(api_key_env, str)
                                    or not api_key_env.replace("_", "").isalnum()):
        raise ValueError("api_key_env names a variable, never the key itself")
    if timeout_seconds is not None and (not isinstance(timeout_seconds, int) or timeout_seconds <= 0):
        raise ValueError("timeout_seconds must be a positive integer")
    p = Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    kept = []
    skipping = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            skipping = s == "[llm]"
            if skipping:
                continue
        if not skipping:
            kept.append(line)
    block = ["[llm]", "provider = " + _q(provider), "model = " + _q(model)]
    if base_url is not None:
        block.append("base_url = " + _q(base_url))
    if api_key_env is not None:
        block.append("api_key_env = " + _q(api_key_env))
    if timeout_seconds is not None:
        block.append("timeout_seconds = %d" % timeout_seconds)
    while kept and not kept[-1].strip():
        kept.pop()
    body = ("\n".join(kept) + "\n\n" if kept else "") + "\n".join(block) + "\n"
    p.write_text(body, encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=None if config_path is None else str(config_path))
    import tomllib
    p = Path("hotdocs.toml") if config_path is None else Path(config_path)
    if not p.exists():
        return None
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("invalid hotdocs.toml: %s" % exc)
    llm = data.get("llm")
    if llm is None:
        return None
    if not isinstance(llm, dict):
        raise ValueError("[llm] must be a table")
    provider = llm.get("provider")
    if provider is not None and provider not in PROVIDERS:
        raise ValueError("unknown provider: %s" % provider)
    return {
        "provider": provider,
        "model": llm.get("model"),
        "base_url": llm.get("base_url"),
        "api_key_env": llm.get("api_key_env"),
        "timeout_seconds": llm.get("timeout_seconds"),
    }
'''


def _make_tool_root(base, req_lines):
    tool = base / "tool"
    log_path = base / "logs" / "llm_endpoint_calls.log"
    mod_dir = tool / "gen" / "llm-endpoint"
    mod_dir.mkdir(parents=True)
    (mod_dir / "llm_endpoint.py").write_text(
        FAKE_LLM_ENDPOINT.replace("__LOG_PATH__", repr(str(log_path))),
        encoding="utf-8",
    )
    slugs = tool / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True)
    (slugs / "slugs.md").write_text(
        "---\nid: P-SLUGS\ntitle: Slugs\nstatus: draft\nowners: [example]\n---\n\n# Slugs\n",
        encoding="utf-8",
    )
    (tool / "requirements.txt").write_text("\n".join(req_lines) + "\n", encoding="utf-8")
    return tool


def _installed_requirements():
    return ["pytest==" + importlib.metadata.version("pytest")]


@pytest.fixture
def command_log(monkeypatch):
    calls = []

    def _recorder(name):
        def _fn(*args, **kwargs):
            calls.append((name, args, kwargs))
            raise RuntimeError("no command may be run by init: %s" % name)
        return _fn

    for name in ("run", "call", "check_call", "check_output", "Popen"):
        monkeypatch.setattr(subprocess, name, _recorder("subprocess." + name))
    monkeypatch.setattr(os, "system", _recorder("os.system"))
    monkeypatch.setattr(os, "popen", _recorder("os.popen"))
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    return calls


def _input_fn(prompt):
    text = str(prompt)
    if text.rstrip().endswith("[y/N]") or text.rstrip().endswith("[Y/n]"):
        return "y"
    return ""


def _run(tool, proj, provider, model, env):
    captured = []

    def output_fn(*args, **kwargs):
        captured.append(" ".join(str(a) for a in args))

    proj.mkdir(parents=True, exist_ok=True)
    argv = [str(proj), "--provider", provider, "--model", model, "--yes", "--no-test"]
    rc = hotdocs_init.main(
        argv,
        tool_root=str(tool),
        input_fn=_input_fn,
        output_fn=output_fn,
        env=env,
        cwd=str(proj),
    )
    lines = []
    for item in captured:
        for line in item.split("\n"):
            lines.append(line.rstrip())
    return rc, lines


def _has_consecutive(lines, first, second):
    for i in range(len(lines) - 1):
        if lines[i] == first and lines[i + 1] == second:
            return True
    return False


def _empty_bin(base, name):
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_missing_requirement_is_reported_and_setup_finishes(tmp_path, command_log, capsys, monkeypatch):
    tool = _make_tool_root(tmp_path, ["pytest==9.2.0", "no-such-pkg-xyz==1.0"])
    proj = tmp_path / "proj"
    monkeypatch.chdir(tmp_path)
    env = {"PATH": str(_empty_bin(tmp_path, "emptybin"))}

    rc, lines = _run(tool, proj, "ollama", "llama3.2", env)

    assert rc == 3, lines
    assert proj.is_dir()
    assert any(proj.iterdir()), "skeleton was not created"
    assert not (proj / "specs" / "product" / "slugs.md").exists()
    assert not (proj / "examples").exists()

    expected_fix = "  fix: pip install -r %s/requirements.txt" % str(tool)
    assert "missing: no-such-pkg-xyz==1.0" in lines, lines
    assert expected_fix in lines, lines
    assert _has_consecutive(lines, "missing: no-such-pkg-xyz==1.0", expected_fix), lines
    assert "missing: pytest==9.2.0" not in lines, lines
    assert "missing: claude on PATH" not in lines, lines

    err = capsys.readouterr().err
    assert "missing:" not in err
    assert command_log == []


def test_missing_claude_reported_for_claude_cli(tmp_path, command_log, capsys, monkeypatch):
    tool = _make_tool_root(tmp_path, _installed_requirements())
    proj = tmp_path / "proj"
    monkeypatch.chdir(tmp_path)
    env = {"PATH": str(_empty_bin(tmp_path, "emptybin"))}

    rc, lines = _run(tool, proj, "claude-cli", "claude-sonnet-5", env)

    assert rc == 3, lines
    assert _has_consecutive(
        lines, "missing: claude on PATH", "  fix: install Claude Code and sign in"
    ), lines
    assert not any(line.startswith("missing: pytest") for line in lines), lines

    err = capsys.readouterr().err
    assert "missing:" not in err
    assert command_log == []


def test_claude_present_on_path_returns_zero(tmp_path, command_log, monkeypatch):
    tool = _make_tool_root(tmp_path, _installed_requirements())
    proj = tmp_path / "proj"
    monkeypatch.chdir(tmp_path)
    bindir = _empty_bin(tmp_path, "bin")
    claude = bindir / "claude"
    claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IRUSR)
    env = {"PATH": str(bindir)}

    rc, lines = _run(tool, proj, "claude-cli", "claude-sonnet-5", env)

    assert rc == 0, lines
    assert "missing: claude on PATH" not in lines, lines
    assert not any(line.startswith("missing:") for line in lines), lines
    assert command_log == []


def test_ollama_without_claude_returns_zero(tmp_path, command_log, monkeypatch):
    tool = _make_tool_root(tmp_path, _installed_requirements())
    proj = tmp_path / "proj"
    monkeypatch.chdir(tmp_path)
    env = {"PATH": str(_empty_bin(tmp_path, "emptybin"))}

    rc, lines = _run(tool, proj, "ollama", "llama3.2", env)

    assert rc == 0, lines
    assert "missing: claude on PATH" not in lines, lines
    assert not any(line.startswith("missing:") for line in lines), lines
    assert command_log == []