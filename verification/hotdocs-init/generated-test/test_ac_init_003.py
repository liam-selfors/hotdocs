import os
import sys
import subprocess
from pathlib import Path

import pytest

import hotdocs_init


pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="host Python below the floor R-INIT-003 assumes is already met",
)


_LLM_ENDPOINT_FAKE = '''
PROVIDERS = {
    "claude-cli": {
        "default_base_url": None,
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
    "ollama": {
        "default_base_url": "http://localhost:11434",
        "default_api_key_env": None,
        "needs_base_url": False,
        "suggested_model": "llama3.1:8b",
    },
}


def detect_providers(env=None, probe_ollama=True):
    results = []
    for name, info in PROVIDERS.items():
        results.append({
            "provider": name,
            "available": True,
            "reason": None,
            "suggested_model": info["suggested_model"],
            "api_key_env": info["default_api_key_env"],
        })
    return results


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    config_path = str(config_path)
    existing = ""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""
    lines = []
    in_llm = False
    for line in existing.splitlines():
        stripped = line.strip()
        if stripped == "[llm]":
            in_llm = True
            continue
        if in_llm and stripped.startswith("[") and stripped != "[llm]":
            in_llm = False
        if not in_llm:
            lines.append(line)
    lines.append("[llm]")
    lines.append("provider = \\"" + provider + "\\"")
    lines.append("model = \\"" + model + "\\"")
    if base_url is not None:
        lines.append("base_url = \\"" + base_url + "\\"")
    if api_key_env is not None:
        lines.append("api_key_env = \\"" + api_key_env + "\\"")
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(timeout_seconds))
    with open(config_path, "w", encoding="utf-8") as f:
        f.write("\\n".join(lines) + "\\n")


def load_config(config_path=None):
    if config_path is None:
        return None
    config_path = str(config_path)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return None
    if "[llm]" not in text:
        return None
    result = {
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
    }
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
                try:
                    value = int(value)
                except ValueError:
                    pass
            if key in result:
                result[key] = value
    return result
'''


_CRITERION_COMPILER_FAKE = (
    "def compile_criterion(*args, **kwargs):\n"
    "    raise NotImplementedError('fake criterion-compiler stub')\n"
)

_SLUGIFY_EXAMPLE_FAKE = "# Slugify Example\n\nFixture placeholder content.\n"


def _build_tool_root(base: Path, requirement_lines):
    tool_root = base / "tool_root"
    (tool_root / "gen" / "llm-endpoint").mkdir(parents=True)
    (tool_root / "gen" / "llm-endpoint" / "llm_endpoint.py").write_text(
        _LLM_ENDPOINT_FAKE, encoding="utf-8"
    )
    (tool_root / "pipeline" / "criterion-compiler").mkdir(parents=True)
    (tool_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py").write_text(
        _CRITERION_COMPILER_FAKE, encoding="utf-8"
    )
    (tool_root / "examples" / "slugify" / "specs" / "product").mkdir(parents=True)
    (tool_root / "examples" / "slugify" / "specs" / "product" / "slugs.md").write_text(
        _SLUGIFY_EXAMPLE_FAKE, encoding="utf-8"
    )
    (tool_root / "requirements.txt").write_text(
        "\n".join(requirement_lines) + "\n", encoding="utf-8"
    )
    return tool_root


def _path_env(*dirs):
    return {"PATH": os.pathsep.join(str(d) for d in dirs)}


def _forbid_commands(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError(
            "R-INIT-003 forbids running a command while checking/reporting prerequisites: "
            + repr(args) + " " + repr(kwargs)
        )

    monkeypatch.setattr(subprocess, "run", _fail)
    monkeypatch.setattr(subprocess, "Popen", _fail)


def _assert_consecutive(lines, first, second):
    for i in range(len(lines) - 1):
        if lines[i] == first and lines[i + 1] == second:
            return
    raise AssertionError(
        "expected consecutive lines %r / %r in %r" % (first, second, lines)
    )


def _blank_input(prompt=""):
    return ""


def test_missing_requirement_reports_but_setup_continues(tmp_path, monkeypatch):
    tool_root = _build_tool_root(tmp_path, ["pytest==9.2.0", "no-such-pkg-xyz==1.0"])
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    _forbid_commands(monkeypatch)

    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()
    env = _path_env(empty_bin)

    output_lines = []
    argv = [str(project_dir), "--provider", "ollama", "--yes", "--no-test"]

    code = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=_blank_input,
        output_fn=output_lines.append,
        env=env,
        cwd=str(project_dir),
    )

    assert code == 3
    assert any(project_dir.iterdir()), (
        "expected the skeleton to be created and the tool vendored despite the missing prerequisite"
    )

    fix_line = "  fix: pip install -r " + str(tool_root) + "/requirements.txt"
    _assert_consecutive(output_lines, "missing: no-such-pkg-xyz==1.0", fix_line)
    assert "missing: pytest==9.2.0" not in output_lines
    assert "missing: Python 3.10 or newer" not in output_lines


def test_claude_cli_missing_from_path(tmp_path, monkeypatch):
    tool_root = _build_tool_root(tmp_path, ["pytest==9.2.0"])
    project_dir = tmp_path / "project_a"
    project_dir.mkdir()

    _forbid_commands(monkeypatch)

    empty_bin = tmp_path / "empty_bin_a"
    empty_bin.mkdir()
    env = _path_env(empty_bin)

    output_lines = []
    argv = [str(project_dir), "--provider", "claude-cli", "--yes", "--no-test"]

    code = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=_blank_input,
        output_fn=output_lines.append,
        env=env,
        cwd=str(project_dir),
    )

    assert code == 3
    _assert_consecutive(
        output_lines, "missing: claude on PATH", "  fix: install Claude Code and sign in"
    )


def test_claude_cli_present_on_path(tmp_path, monkeypatch):
    tool_root = _build_tool_root(tmp_path, ["pytest==9.2.0"])
    project_dir = tmp_path / "project_b"
    project_dir.mkdir()

    _forbid_commands(monkeypatch)

    bin_with_claude = tmp_path / "bin_with_claude"
    bin_with_claude.mkdir()
    (bin_with_claude / "claude").write_text("fake claude executable\n", encoding="utf-8")
    env = _path_env(bin_with_claude)

    output_lines = []
    argv = [str(project_dir), "--provider", "claude-cli", "--yes", "--no-test"]

    code = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=_blank_input,
        output_fn=output_lines.append,
        env=env,
        cwd=str(project_dir),
    )

    assert code == 0
    assert "missing: claude on PATH" not in output_lines


def test_ollama_provider_skips_claude_check(tmp_path, monkeypatch):
    tool_root = _build_tool_root(tmp_path, ["pytest==9.2.0"])
    project_dir = tmp_path / "project_c"
    project_dir.mkdir()

    _forbid_commands(monkeypatch)

    empty_bin = tmp_path / "empty_bin_c"
    empty_bin.mkdir()
    env = _path_env(empty_bin)

    output_lines = []
    argv = [str(project_dir), "--provider", "ollama", "--yes", "--no-test"]

    code = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=_blank_input,
        output_fn=output_lines.append,
        env=env,
        cwd=str(project_dir),
    )

    assert code == 0
    assert "missing: claude on PATH" not in output_lines