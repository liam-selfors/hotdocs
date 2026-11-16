import importlib.metadata
import json
import os
import sys
from pathlib import Path

import pytest

import hotdocs_init


PROVIDER_KEYS = [
    "claude-cli",
    "anthropic",
    "openai",
    "openai-compatible",
    "gemini",
    "ollama",
]

# Built by concatenation so the test source holds no secret-shaped literal.
PASTED_KEY = "sk" + "-" + "abc123"


FAKE_LLM_ENDPOINT = r'''
import json as _json
import re as _re
from pathlib import Path as _Path

_LOG = __LOG_PATH__

_ENV_NAME = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _log(name, **kwargs):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(
            _json.dumps({"fn": name, "args": {k: repr(v) for k, v in kwargs.items()}})
            + "\n"
        )


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
    _log(
        "detect_providers",
        env_keys=None if env is None else sorted(env.keys()),
        probe_ollama=probe_ollama,
    )
    result = []
    for name, info in PROVIDERS.items():
        result.append(
            {
                "provider": name,
                "available": True,
                "reason": "fake: available",
                "suggested_model": info["suggested_model"],
                "api_key_env": info["default_api_key_env"],
            }
        )
    return result


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log(
        "check_connection",
        provider=provider,
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
    )
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url is required")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log(
        "save_config",
        config_path=str(config_path),
        provider=provider,
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
    )
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if not isinstance(model, str) or not model:
        raise ValueError("model is required")
    if api_key_env is not None and not _ENV_NAME.match(str(api_key_env)):
        raise ValueError("api_key_env must name a variable, never the key itself")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url is required")
    if provider == "claude-cli" and (base_url or api_key_env):
        raise ValueError("claude-cli takes no base_url or api_key_env")
    path = _Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if path.exists():
        in_llm = False
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_llm = stripped == "[llm]"
                if in_llm:
                    continue
            if not in_llm:
                kept.append(line)
    lines = list(kept)
    if lines and lines[-1].strip():
        lines.append("")
    lines.append("[llm]")
    lines.append('provider = "%s"' % provider)
    lines.append('model = "%s"' % model)
    if base_url is not None:
        lines.append('base_url = "%s"' % base_url)
    if api_key_env is not None:
        lines.append('api_key_env = "%s"' % api_key_env)
    if timeout_seconds is not None:
        lines.append("timeout_seconds = %d" % int(timeout_seconds))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=None if config_path is None else str(config_path))
    if config_path is None:
        config_path = _Path.cwd() / "hotdocs.toml"
    path = _Path(config_path)
    if not path.exists():
        return None
    values = {}
    found = False
    in_llm = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_llm = stripped == "[llm]"
            found = found or in_llm
            continue
        if in_llm and "=" in stripped and not stripped.startswith("#"):
            key, _, raw = stripped.partition("=")
            key = key.strip()
            raw = raw.strip()
            if raw.startswith('"') and raw.endswith('"'):
                values[key] = raw[1:-1]
            else:
                try:
                    values[key] = int(raw)
                except ValueError:
                    raise ValueError("invalid value for " + key)
    if not found:
        return None
    if values.get("provider") not in PROVIDERS:
        raise ValueError("invalid provider")
    return {
        "provider": values.get("provider"),
        "model": values.get("model"),
        "base_url": values.get("base_url"),
        "api_key_env": values.get("api_key_env"),
        "timeout_seconds": values.get("timeout_seconds"),
    }
'''


SLUGS_MD = """---
id: P-SLUGIFY
title: Slugs
status: draft
owners: [example-owner]
---

# Slugs

A slug is a lowercase, hyphen-separated form of a title.
"""


def _build_tool_root(base: Path) -> tuple[Path, Path]:
    tool_root = base / "tool"
    log_dir = base / "logs"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "llm_endpoint_calls.jsonl"

    endpoint_dir = tool_root / "gen" / "llm-endpoint"
    endpoint_dir.mkdir(parents=True)
    (endpoint_dir / "llm_endpoint.py").write_text(
        FAKE_LLM_ENDPOINT.replace("__LOG_PATH__", repr(str(log_path))),
        encoding="utf-8",
    )

    slugs = tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md"
    slugs.parent.mkdir(parents=True)
    slugs.write_text(SLUGS_MD, encoding="utf-8")

    (tool_root / "requirements.txt").write_text(
        "pytest==" + importlib.metadata.version("pytest") + "\n",
        encoding="utf-8",
    )
    return tool_root, log_path


def _snapshot(root: Path) -> dict:
    result = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_dir():
            result[rel + "/"] = None
        else:
            result[rel] = p.read_bytes()
    return result


def _env() -> dict:
    return {"PATH": os.environ.get("PATH", "")}


class _Recorder:
    def __init__(self):
        self.lines = []

    def __call__(self, *args, **kwargs):
        self.lines.append(" ".join(str(a) for a in args))

    def text(self) -> str:
        return "\n".join(self.lines)


def _no_input(prompt=""):
    return "y"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    tool_root, log_path = _build_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    return tool_root, log_path, project


def _run_usage(argv, tool_root, project, capsys):
    recorder = _Recorder()
    capsys.readouterr()
    before = _snapshot(project)
    rc = hotdocs_init.main(
        argv,
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=recorder,
        env=_env(),
        cwd=project,
    )
    captured = capsys.readouterr()
    after = _snapshot(project)
    combined = recorder.text() + "\n" + captured.out + "\n" + captured.err
    return rc, before, after, combined


@pytest.mark.parametrize(
    "argv",
    [
        ["--bogus"],
        ["--provider"],
        ["a", "b"],
        ["--provider", "nope"],
        ["--provider=openai", "--model"],
    ],
)
def test_usage_errors_exit_2_and_write_nothing(argv, setup, capsys):
    tool_root, log_path, project = setup
    rc, before, after, _ = _run_usage(list(argv), tool_root, project, capsys)
    assert rc == 2
    assert after == before, "a usage error must write nothing under <dir>"
    assert not (project / "a").exists()
    assert not (project / "b").exists()


def test_unknown_provider_message_lists_provider_keys(setup, capsys):
    tool_root, log_path, project = setup
    rc, before, after, combined = _run_usage(
        ["--provider", "nope"], tool_root, project, capsys
    )
    assert rc == 2
    assert after == before
    for key in PROVIDER_KEYS:
        assert key in combined, f"provider key {key!r} missing from message: {combined!r}"


@pytest.mark.parametrize(
    "argv",
    [
        ["--provider", "openai", "--api-key-env", PASTED_KEY],
        ["--provider", "openai", "--api-key-env", "9X"],
    ],
)
def test_invalid_api_key_env_exit_2_never_echoed(argv, setup, capsys):
    tool_root, log_path, project = setup
    rc, before, after, combined = _run_usage(list(argv), tool_root, project, capsys)
    assert rc == 2
    assert after == before, "an invalid --api-key-env must write nothing"
    assert PASTED_KEY not in combined
    if log_path.exists():
        assert PASTED_KEY not in log_path.read_text(encoding="utf-8")
    for path in project.rglob("*"):
        if path.is_file():
            assert PASTED_KEY.encode() not in path.read_bytes()


@pytest.mark.parametrize(
    "argv",
    [
        ["--provider", "claude-cli", "--base-url", "http://h"],
        ["--provider", "claude-cli", "--api-key-env", "K"],
    ],
)
def test_claude_cli_rejects_base_url_and_api_key_env(argv, setup, capsys):
    tool_root, log_path, project = setup
    rc, before, after, _ = _run_usage(list(argv), tool_root, project, capsys)
    assert rc == 2
    assert after == before


@pytest.mark.parametrize(
    "argv",
    [
        ["--provider", "openai-compatible", "--base-url", "http://h"],
        ["--provider", "openai-compatible", "--model", "m"],
    ],
)
def test_openai_compatible_needs_model_and_base_url(argv, setup, capsys):
    tool_root, log_path, project = setup
    rc, before, after, _ = _run_usage(list(argv), tool_root, project, capsys)
    assert rc == 2
    assert after == before


@pytest.mark.parametrize(
    "flags",
    [
        ["--provider", "openai", "--yes"],
        ["--yes", "--provider", "openai"],
        ["--provider=openai", "--yes"],
        ["--yes", "--provider=openai"],
    ],
)
def test_valid_provider_and_yes_returns_0(flags, tmp_path, monkeypatch, capsys):
    tool_root, log_path = _build_tool_root(tmp_path)
    project = tmp_path / "proj"
    project.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    env = _env()
    env["OPENAI_API_KEY"] = "placeholder"

    recorder = _Recorder()
    rc = hotdocs_init.main(
        list(flags) + [str(project)],
        tool_root=tool_root,
        input_fn=_no_input,
        output_fn=recorder,
        env=env,
        cwd=elsewhere,
    )
    captured = capsys.readouterr()
    assert rc == 0, (
        "expected exit 0; output was:\n"
        + recorder.text()
        + "\nstdout:\n"
        + captured.out
        + "\nstderr:\n"
        + captured.err
    )