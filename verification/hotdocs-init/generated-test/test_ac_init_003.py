import contextlib
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

import pytest

import hotdocs_init

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="AC-INIT-003's zero-missing-prerequisite assertions require running under Python 3.11+",
)

_LLM_ENDPOINT_TEMPLATE = '''
import json
from pathlib import Path

PROVIDERS = {
    "claude-cli": {"default_base_url": None, "default_api_key_env": None, "needs_base_url": False, "suggested_model": "claude-test-model"},
    "ollama": {"default_base_url": "http://localhost:11434", "default_api_key_env": None, "needs_base_url": False, "suggested_model": "llama-test-model"},
    "anthropic": {"default_base_url": None, "default_api_key_env": "ANTHROPIC_API_KEY", "needs_base_url": False, "suggested_model": "claude-test-model"},
    "openai": {"default_base_url": None, "default_api_key_env": "OPENAI_API_KEY", "needs_base_url": False, "suggested_model": "gpt-test-model"},
    "openai-compatible": {"default_base_url": None, "default_api_key_env": None, "needs_base_url": True, "suggested_model": ""},
    "gemini": {"default_base_url": None, "default_api_key_env": "GEMINI_API_KEY", "needs_base_url": False, "suggested_model": "gemini-test-model"},
}

_LOG_PATH = "__LOG_PATH__"

def _log(record):
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\\n")

def detect_providers(env=None, probe_ollama=True):
    _log({"call": "detect_providers", "had_env": env is not None, "probe_ollama": probe_ollama})
    return [
        {
            "provider": name,
            "available": False,
            "reason": "fake-not-available",
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        }
        for name, info in PROVIDERS.items()
    ]

def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log({"call": "check_connection", "provider": provider, "model": model})
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required for provider: " + str(provider))
    return {"ok": True, "error": None}

def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log({"call": "save_config", "provider": provider, "model": model})
    path = Path(config_path)
    existing_text = path.read_text() if path.exists() else ""
    kept_lines = []
    skipping = False
    for line in existing_text.splitlines():
        stripped = line.strip()
        if stripped == "[llm]":
            skipping = True
            continue
        if skipping and stripped.startswith("[") and stripped != "[llm]":
            skipping = False
        if not skipping:
            kept_lines.append(line)
    block_lines = ["[llm]", 'provider = "' + provider + '"', 'model = "' + model + '"']
    if base_url:
        block_lines.append('base_url = "' + base_url + '"')
    if api_key_env:
        block_lines.append('api_key_env = "' + api_key_env + '"')
    if timeout_seconds is not None:
        block_lines.append("timeout_seconds = " + str(timeout_seconds))
    new_text = "\\n".join(kept_lines + block_lines) + "\\n"
    path.write_text(new_text)

def load_config(config_path=None):
    _log({"call": "load_config", "config_path": str(config_path)})
    if config_path is None:
        return None
    path = Path(config_path)
    if not path.exists():
        return None
    text = path.read_text()
    if "[llm]" not in text:
        return None
    result = {"provider": None, "model": None, "base_url": None, "api_key_env": None, "timeout_seconds": None}
    in_llm = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[llm]":
            in_llm = True
            continue
        if stripped.startswith("[") and stripped != "[llm]":
            in_llm = False
            continue
        if in_llm and "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip('"')
            if key == "timeout_seconds":
                result[key] = int(value) if value else None
            elif key in result:
                result[key] = value if value else None
    return result
'''


def _build_tool_root(tool_root, requirements_lines, log_path):
    tool_root.mkdir(parents=True, exist_ok=True)
    (tool_root / "requirements.txt").write_text("\n".join(requirements_lines) + "\n")
    gen_dir = tool_root / "gen" / "llm-endpoint"
    gen_dir.mkdir(parents=True, exist_ok=True)
    source = _LLM_ENDPOINT_TEMPLATE.replace("__LOG_PATH__", str(log_path))
    (gen_dir / "llm_endpoint.py").write_text(source)
    examples_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    examples_dir.mkdir(parents=True, exist_ok=True)
    (examples_dir / "slugs.md").write_text("fake slugify example content\n")


@contextlib.contextmanager
def _forbid_commands():
    orig_run = subprocess.run
    orig_popen = subprocess.Popen
    orig_system = os.system

    def _blocked_run(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called by init's prerequisite check")

    def _blocked_popen(*args, **kwargs):
        raise AssertionError("subprocess.Popen must not be called by init's prerequisite check")

    def _blocked_system(*args, **kwargs):
        raise AssertionError("os.system must not be called by init's prerequisite check")

    subprocess.run = _blocked_run
    subprocess.Popen = _blocked_popen
    os.system = _blocked_system
    try:
        yield
    finally:
        subprocess.run = orig_run
        subprocess.Popen = orig_popen
        os.system = orig_system


def _refusing_input_fn(prompt):
    raise AssertionError("unexpected input_fn prompt: " + repr(prompt))


def _find_consecutive(lines, first, second):
    for i in range(len(lines) - 1):
        if lines[i] == first and lines[i + 1] == second:
            return i
    return -1


def test_missing_requirement_reported_and_no_command_run(tmp_path):
    tool_root = tmp_path / "tool_root"
    project_dir = tmp_path / "project"
    log_path = tmp_path / "llm_calls_1.log"
    _build_tool_root(
        tool_root,
        requirements_lines=["pytest==9.2.0", "no-such-pkg-xyz==1.0"],
        log_path=log_path,
    )
    tool_root_str = str(tool_root)

    output_lines = []

    def output_fn(message):
        output_lines.append(message)

    assert not project_dir.exists()

    with _forbid_commands():
        rc = hotdocs_init.main(
            [str(project_dir), "--provider", "ollama", "--model", "test-model", "--no-test", "--yes"],
            tool_root=tool_root_str,
            input_fn=_refusing_input_fn,
            output_fn=output_fn,
            env={"PATH": str(tmp_path / "no_claude_bin")},
            cwd=str(tmp_path),
        )

    assert rc == 3
    assert project_dir.exists()
    assert any(project_dir.iterdir())

    expected_fix = "  fix: pip install -r " + tool_root_str + "/requirements.txt"
    idx = _find_consecutive(output_lines, "missing: no-such-pkg-xyz==1.0", expected_fix)
    assert idx >= 0, "expected consecutive lines not found in output_fn calls: %r" % (output_lines,)


def test_claude_on_path_checked_only_for_claude_cli_provider(tmp_path):
    tool_root = tmp_path / "tool_root"
    log_path = tmp_path / "llm_calls_2.log"
    installed_pytest_version = importlib.metadata.version("pytest")
    _build_tool_root(
        tool_root,
        requirements_lines=["pytest==" + installed_pytest_version],
        log_path=log_path,
    )
    tool_root_str = str(tool_root)

    no_claude_dir = tmp_path / "no_claude_bin"
    no_claude_dir.mkdir()

    # Part A: provider claude-cli, no claude on PATH -> rc == 3, two consecutive lines reported.
    project_a = tmp_path / "project_a"
    output_lines_a = []

    def output_fn_a(message):
        output_lines_a.append(message)

    rc_a = hotdocs_init.main(
        [str(project_a), "--provider", "claude-cli", "--model", "test-model", "--no-test", "--yes"],
        tool_root=tool_root_str,
        input_fn=_refusing_input_fn,
        output_fn=output_fn_a,
        env={"PATH": str(no_claude_dir)},
        cwd=str(tmp_path),
    )

    assert rc_a == 3
    idx_a = _find_consecutive(
        output_lines_a,
        "missing: claude on PATH",
        "  fix: install Claude Code and sign in",
    )
    assert idx_a >= 0, "expected consecutive claude-missing lines not found in: %r" % (output_lines_a,)

    # Part B: same provider, but with an executable "claude" file on PATH -> rc == 0.
    bin_with_claude = tmp_path / "bin_with_claude"
    bin_with_claude.mkdir()
    claude_executable = bin_with_claude / "claude"
    claude_executable.write_text("#!/bin/sh\necho fake-claude\n")
    claude_executable.chmod(0o755)

    project_b = tmp_path / "project_b"
    output_lines_b = []

    def output_fn_b(message):
        output_lines_b.append(message)

    rc_b = hotdocs_init.main(
        [str(project_b), "--provider", "claude-cli", "--model", "test-model", "--no-test", "--yes"],
        tool_root=tool_root_str,
        input_fn=_refusing_input_fn,
        output_fn=output_fn_b,
        env={"PATH": str(bin_with_claude)},
        cwd=str(tmp_path),
    )

    assert rc_b == 0
    assert "missing: claude on PATH" not in output_lines_b

    # Part C: provider ollama, no claude on PATH -> rc == 0 (claude check skipped for this provider).
    project_c = tmp_path / "project_c"
    output_lines_c = []

    def output_fn_c(message):
        output_lines_c.append(message)

    rc_c = hotdocs_init.main(
        [str(project_c), "--provider", "ollama", "--model", "test-model", "--no-test", "--yes"],
        tool_root=tool_root_str,
        input_fn=_refusing_input_fn,
        output_fn=output_fn_c,
        env={"PATH": str(no_claude_dir)},
        cwd=str(tmp_path),
    )

    assert rc_c == 0
    assert "missing: claude on PATH" not in output_lines_c