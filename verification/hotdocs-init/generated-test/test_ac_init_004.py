import importlib.metadata
import json
import os
import stat
import sys
from pathlib import Path

import pytest

import hotdocs_init


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


_FAKE_TEMPLATE = r'''
import json
import os
from pathlib import Path

_LOG = __LOG__
_DETECT = json.loads(__DETECT__)
PROVIDERS = json.loads(__PROVIDERS__)

_UNSET = object()


def _log(name, **data):
    rec = {"call": name}
    rec.update(data)
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    return [dict(p) for p in _DETECT]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection", provider=provider, model=model, base_url=base_url,
         api_key_env=api_key_env)
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=_UNSET, api_key_env=_UNSET,
                timeout_seconds=_UNSET):
    _log(
        "save_config",
        config_path=str(config_path),
        provider=provider,
        model=model,
        base_url_passed=base_url is not _UNSET,
        base_url=None if base_url is _UNSET else base_url,
        api_key_env_passed=api_key_env is not _UNSET,
        api_key_env=None if api_key_env is _UNSET else api_key_env,
        timeout_seconds_passed=timeout_seconds is not _UNSET,
    )
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[llm]", 'provider = "%s"' % provider, 'model = "%s"' % model]
    if base_url is not _UNSET and base_url is not None:
        lines.append('base_url = "%s"' % base_url)
    if api_key_env is not _UNSET and api_key_env is not None:
        lines.append('api_key_env = "%s"' % api_key_env)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return None


def load_config(config_path=None):
    _log("load_config", config_path=str(config_path))
    path = Path(config_path) if config_path is not None else Path("hotdocs.toml")
    if not path.exists():
        return None
    result = {"provider": None, "model": None, "base_url": None,
              "api_key_env": None, "timeout_seconds": None}
    in_llm = False
    found = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("["):
            in_llm = line == "[llm]"
            if in_llm:
                found = True
            continue
        if in_llm and "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"')
            if k in result:
                result[k] = v
    if not found:
        return None
    return result
'''


def _all_providers(overrides=None):
    providers = {
        "claude-cli": {"default_base_url": None, "default_api_key_env": None,
                       "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
        "anthropic": {"default_base_url": "https://api.anthropic.com",
                      "default_api_key_env": "ANTHROPIC_API_KEY",
                      "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
        "openai": {"default_base_url": "https://api.openai.com/v1",
                   "default_api_key_env": "OPENAI_API_KEY",
                   "needs_base_url": False, "suggested_model": "gpt-x"},
        "openai-compatible": {"default_base_url": None, "default_api_key_env": None,
                              "needs_base_url": True, "suggested_model": ""},
        "gemini": {"default_base_url": "https://generativelanguage.googleapis.com",
                   "default_api_key_env": "GEMINI_API_KEY",
                   "needs_base_url": False, "suggested_model": "gemini-4-argon"},
        "ollama": {"default_base_url": "http://localhost:11434",
                   "default_api_key_env": None,
                   "needs_base_url": False, "suggested_model": "llama3.2"},
    }
    if overrides:
        providers.update(overrides)
    return providers


OLLAMA_UNAVAILABLE = {"provider": "ollama", "available": False, "reason": "not running",
                      "suggested_model": "llama3.2", "api_key_env": None}
OPENAI_AVAILABLE = {"provider": "openai", "available": True, "reason": "ready",
                    "suggested_model": "gpt-x", "api_key_env": "OPENAI_API_KEY"}


def _make_tool_root(base, log_path, detect, providers=None, with_endpoint=True):
    root = base / "toolroot"
    root.mkdir(parents=True, exist_ok=True)
    pytest_version = importlib.metadata.version("pytest")
    (root / "requirements.txt").write_text("pytest==%s\n" % pytest_version, encoding="utf-8")
    slugs = root / "examples" / "slugify" / "specs" / "product"
    slugs.mkdir(parents=True, exist_ok=True)
    (slugs / "slugs.md").write_text("# Slugs\n\nTurn titles into slugs.\n", encoding="utf-8")
    if with_endpoint:
        ep = root / "gen" / "llm-endpoint"
        ep.mkdir(parents=True, exist_ok=True)
        src = (
            _FAKE_TEMPLATE
            .replace("__LOG__", repr(str(log_path)))
            .replace("__DETECT__", repr(json.dumps(detect)))
            .replace("__PROVIDERS__", repr(json.dumps(providers or _all_providers())))
        )
        (ep / "llm_endpoint.py").write_text(src, encoding="utf-8")
    return root


def _make_env(base, with_claude=False):
    bindir = base / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    if with_claude:
        claude = bindir / "claude"
        claude.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    home = base / "home"
    home.mkdir(parents=True, exist_ok=True)
    return {"PATH": str(bindir), "HOME": str(home)}


def _read_log(log_path):
    if not Path(log_path).exists():
        return []
    out = []
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _saves(log_path):
    return [r for r in _read_log(log_path) if r.get("call") == "save_config"]


class _Inputs:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt=""):
        self.prompts.append(str(prompt))
        if len(self.prompts) > 100:
            raise RuntimeError("too many questions asked")
        if self.answers:
            return self.answers.pop(0)
        return ""


def _classify(prompt):
    low = prompt.lower()
    if "url" in low:
        return "base_url"
    if "key" in low:
        return "api_key"
    if "model" in low:
        return "model"
    if "provider" in low:
        return "provider"
    return None


def _kinds(prompts):
    return [k for k in (_classify(p) for p in prompts) if k is not None]


def _run(tmp_path, argv_extra, answers, detect, providers=None, with_endpoint=True,
         with_claude=False, project=None):
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "calls.jsonl"
    tool_root = _make_tool_root(tmp_path, log_path, detect, providers, with_endpoint)
    if project is None:
        project = tmp_path / "proj"
        project.mkdir(parents=True, exist_ok=True)
    env = _make_env(tmp_path, with_claude=with_claude)
    inputs = _Inputs(answers)
    outputs = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    code = hotdocs_init.main(
        [str(project)] + list(argv_extra),
        tool_root=tool_root,
        input_fn=inputs,
        output_fn=output_fn,
        env=env,
        cwd=project,
    )
    return code, inputs, outputs, log_path, project


def test_interactive_defaults_ask_provider_model_key_and_save_openai(tmp_path):
    code, inputs, outputs, log_path, project = _run(
        tmp_path, [], [], [OLLAMA_UNAVAILABLE, OPENAI_AVAILABLE]
    )
    kinds = _kinds(inputs.prompts)
    assert kinds == ["provider", "model", "api_key"], inputs.prompts
    text = "\n".join(outputs)
    assert "ollama" in text
    assert "openai" in text
    saves = _saves(log_path)
    assert len(saves) == 1, saves
    s = saves[0]
    assert s["provider"] == "openai"
    assert s["model"] == "gpt-x"
    assert s["api_key_env_passed"] is True
    assert s["api_key_env"] == "OPENAI_API_KEY"
    assert s["timeout_seconds_passed"] is False
    assert Path(s["config_path"]).name == "hotdocs.toml"
    detects = [r for r in _read_log(log_path) if r.get("call") == "detect_providers"]
    assert detects and all(r["env_given"] for r in detects)


def test_unrecognised_provider_answer_is_asked_again_and_number_selects(tmp_path):
    code, inputs, outputs, log_path, project = _run(
        tmp_path, [], ["bogus", "2"], [OLLAMA_UNAVAILABLE, OPENAI_AVAILABLE]
    )
    kinds = _kinds(inputs.prompts)
    assert kinds[:2] == ["provider", "provider"], inputs.prompts
    assert kinds.count("provider") == 2, inputs.prompts
    assert kinds[2:] == ["model", "api_key"], inputs.prompts
    saves = _saves(log_path)
    assert len(saves) == 1, saves
    assert saves[0]["provider"] == "openai"
    assert saves[0]["model"] == "gpt-x"
    assert saves[0]["timeout_seconds_passed"] is False


def test_openai_compatible_asks_model_and_base_url_again_when_empty(tmp_path):
    detect = [
        OLLAMA_UNAVAILABLE,
        {"provider": "openai-compatible", "available": True, "reason": "configurable",
         "suggested_model": "", "api_key_env": None},
    ]
    providers = _all_providers({
        "openai-compatible": {"default_base_url": None, "default_api_key_env": None,
                              "needs_base_url": True, "suggested_model": ""},
    })
    answers = ["openai-compatible", "", "m", "", "http://h/v1", ""]
    code, inputs, outputs, log_path, project = _run(
        tmp_path, [], answers, detect, providers=providers
    )
    kinds = _kinds(inputs.prompts)
    assert kinds == ["provider", "model", "model", "base_url", "base_url", "api_key"], \
        inputs.prompts
    saves = _saves(log_path)
    assert len(saves) == 1, saves
    s = saves[0]
    assert s["provider"] == "openai-compatible"
    assert s["model"] == "m"
    assert s["base_url"] == "http://h/v1"
    assert s["api_key_env_passed"] is False
    assert s["timeout_seconds_passed"] is False


def test_claude_cli_asks_no_base_url_or_api_key_and_returns_zero(tmp_path):
    detect = [
        {"provider": "claude-cli", "available": True, "reason": "claude on PATH",
         "suggested_model": "claude-sonnet-5", "api_key_env": None},
        OLLAMA_UNAVAILABLE,
    ]
    code, inputs, outputs, log_path, project = _run(
        tmp_path, [], [], detect, with_claude=True
    )
    kinds = _kinds(inputs.prompts)
    assert "base_url" not in kinds, inputs.prompts
    assert "api_key" not in kinds, inputs.prompts
    assert kinds[:2] == ["provider", "model"], inputs.prompts
    assert code == 0
    saves = _saves(log_path)
    assert len(saves) == 1, saves
    assert saves[0]["provider"] == "claude-cli"
    assert saves[0]["model"] == "claude-sonnet-5"
    assert saves[0]["timeout_seconds_passed"] is False


def test_missing_llm_endpoint_reports_and_carries_on(tmp_path):
    code, inputs, outputs, log_path, project = _run(
        tmp_path, ["--yes"], [], [OPENAI_AVAILABLE], with_endpoint=False
    )
    msg = "provider not configured: gen/llm-endpoint is missing"
    assert any(msg in o for o in outputs), outputs
    assert code == 0
    assert not (project / "hotdocs.toml").exists()


def test_existing_hotdocs_toml_skips_provider_step(tmp_path):
    project = tmp_path / "proj"
    project.mkdir(parents=True, exist_ok=True)
    original = b'[llm]\nprovider = "ollama"\nmodel = "llama3.2"\n'
    (project / "hotdocs.toml").write_bytes(original)
    code, inputs, outputs, log_path, project = _run(
        tmp_path, [], [], [OLLAMA_UNAVAILABLE, OPENAI_AVAILABLE], project=project
    )
    assert _saves(log_path) == []
    assert (project / "hotdocs.toml").read_bytes() == original
    kinds = _kinds(inputs.prompts)
    assert "provider" not in kinds, inputs.prompts
    assert any("hotdocs.toml" in o for o in outputs), outputs