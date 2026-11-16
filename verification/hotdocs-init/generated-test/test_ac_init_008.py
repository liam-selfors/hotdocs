import importlib.metadata
import json
import os
import sys
from pathlib import Path

import pytest

import hotdocs_init


EXPECTED_ALLOWLIST = (
    json.dumps({"version": 1, "entries": []}, indent=2) + "\n"
).encode("utf-8")

SKIP_MESSAGE = ".secret-allowlist.json: skipped (exists)"


FAKE_LLM_ENDPOINT_TEMPLATE = '''
import json
from pathlib import Path

_LOG_PATH = {log_path!r}


def _log(name, **kwargs):
    record = {{"call": name}}
    for key, value in kwargs.items():
        try:
            json.dumps(value)
            record[key] = value
        except (TypeError, ValueError):
            record[key] = repr(value)
    with open(_LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\\n")


PROVIDERS = {{
    "claude-cli": {{
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    }},
    "anthropic": {{
        "default_base_url": "https://api.anthropic.com",
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    }},
    "openai": {{
        "default_base_url": "https://api.openai.com/v1",
        "default_api_key_env": "OPENAI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gpt-6-astra",
    }},
    "openai-compatible": {{
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": True,
        "suggested_model": "",
    }},
    "gemini": {{
        "default_base_url": "https://generativelanguage.googleapis.com",
        "default_api_key_env": "GEMINI_API_KEY",
        "needs_base_url": False,
        "suggested_model": "gemini-4-argon",
    }},
    "ollama": {{
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.2",
    }},
}}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", env_given=env is not None, probe_ollama=probe_ollama)
    result = []
    for name, info in PROVIDERS.items():
        available = name == "ollama"
        result.append({{
            "provider": name,
            "available": available,
            "reason": "reachable" if available else "not configured",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        }})
    return result


def check_connection(provider, model, base_url=None, api_key_env=None,
                     timeout_seconds=30):
    _log("check_connection", provider=provider, model=model,
         base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds)
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {{"ok": True, "error": None}}


def _toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value))


def save_config(config_path, provider, model, base_url=None,
                api_key_env=None, timeout_seconds=None):
    _log("save_config", config_path=str(config_path), provider=provider,
         model=model, base_url=base_url, api_key_env=api_key_env,
         timeout_seconds=timeout_seconds)
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
                if in_llm:
                    continue
            if not in_llm:
                kept.append(line)
    lines = list(kept)
    if lines and lines[-1].strip():
        lines.append("")
    lines.append("[llm]")
    lines.append("provider = " + _toml_value(provider))
    lines.append("model = " + _toml_value(model))
    if base_url is not None:
        lines.append("base_url = " + _toml_value(base_url))
    if api_key_env is not None:
        lines.append("api_key_env = " + _toml_value(api_key_env))
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + _toml_value(int(timeout_seconds)))
    path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def load_config(config_path=None):
    _log("load_config", config_path=None if config_path is None else str(config_path))
    if config_path is None:
        return None
    path = Path(config_path)
    if not path.exists():
        return None
    result = {{
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
    }}
    found = False
    in_llm = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_llm = stripped == "[llm]"
            found = found or in_llm
            continue
        if not in_llm or "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        key = key.strip()
        raw = raw.strip()
        if key not in result:
            continue
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw
        result[key] = value
    if not found:
        return None
    return result
'''


def _make_fake_tool_root(base: Path, log_path: Path) -> Path:
    tool_root = base / "tool"
    llm_dir = tool_root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    (llm_dir / "llm_endpoint.py").write_text(
        FAKE_LLM_ENDPOINT_TEMPLATE.format(log_path=str(log_path)),
        encoding="utf-8",
    )

    other_dir = tool_root / "gen" / "spec-linter"
    other_dir.mkdir(parents=True)
    (other_dir / "spec_linter.py").write_text(
        "def lint(paths=None, repo_root=None):\n    return []\n",
        encoding="utf-8",
    )

    slugs_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    slugs_dir.mkdir(parents=True)
    (slugs_dir / "slugs.md").write_text(
        "# Slugs\n\nA tiny example product.\n", encoding="utf-8"
    )

    pytest_version = importlib.metadata.version("pytest")
    (tool_root / "requirements.txt").write_text(
        "pytest==" + pytest_version + "\n", encoding="utf-8"
    )
    return tool_root


def _setup(tmp_path: Path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "llm_calls.log"
    tool_root = _make_fake_tool_root(tmp_path, log_path)
    project = tmp_path / "proj"
    project.mkdir()
    return tool_root, project, log_path


def _env():
    env = {"PATH": os.environ.get("PATH", "")}
    if "HOME" in os.environ:
        env["HOME"] = os.environ["HOME"]
    return env


def _run(project: Path, tool_root: Path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    outputs = []
    prompts = []

    def output_fn(*args, **kwargs):
        outputs.append(" ".join(str(a) for a in args))

    def input_fn(prompt=""):
        prompts.append(prompt)
        return ""

    code = hotdocs_init.main(
        [str(project), "--yes"],
        tool_root=tool_root,
        input_fn=input_fn,
        output_fn=output_fn,
        env=_env(),
        cwd=str(project),
    )
    return code, outputs, prompts


def _output_lines(outputs):
    lines = []
    for message in outputs:
        for line in str(message).splitlines():
            lines.append(line.strip())
    return lines


def test_creates_empty_allowlist_with_exact_bytes_and_no_decision_files(
    tmp_path, monkeypatch
):
    tool_root, project, _log_path = _setup(tmp_path)

    code, outputs, _prompts = _run(project, tool_root, monkeypatch)

    assert code in (0, 3), (code, outputs)

    allowlist = project / ".secret-allowlist.json"
    assert allowlist.is_file(), outputs
    assert allowlist.read_bytes() == EXPECTED_ALLOWLIST

    decisions = project / "specs" / "decisions"
    assert decisions.is_dir(), outputs
    entries = sorted(p.name for p in decisions.iterdir())
    assert entries == [".gitkeep"], entries


def test_existing_allowlist_is_skipped_and_unchanged(tmp_path, monkeypatch):
    tool_root, project, _log_path = _setup(tmp_path)

    original = b'{\n  "version": 1,\n  "entries": [\n    {"path": "docs/x.md", "note": "kept"}\n  ]\n}\n'
    allowlist = project / ".secret-allowlist.json"
    allowlist.write_bytes(original)

    code, outputs, _prompts = _run(project, tool_root, monkeypatch)

    assert code in (0, 3), (code, outputs)
    assert allowlist.read_bytes() == original

    lines = _output_lines(outputs)
    assert SKIP_MESSAGE in lines, outputs

    decisions = project / "specs" / "decisions"
    if decisions.exists():
        entries = sorted(p.name for p in decisions.iterdir())
        assert entries == [".gitkeep"], entries