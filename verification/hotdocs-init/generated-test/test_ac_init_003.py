import importlib.metadata
import os
import stat
import textwrap
import unittest.mock as mock

import hotdocs_init


_LLM_ENDPOINT_TEMPLATE = textwrap.dedent('''
import json
import os

PROVIDERS = {
    "claude-cli": {"default_base_url": None, "default_api_key_env": None,
                   "needs_base_url": False, "suggested_model": "claude-sonnet-5"},
    "ollama": {"default_base_url": "http://localhost:11434", "default_api_key_env": None,
               "needs_base_url": False, "suggested_model": "llama3.1:8b"},
}

LOG_PATH = __LOG_PATH__


def _log(name, info):
    with open(LOG_PATH, "a") as f:
        f.write(name + " " + repr(info))
        f.write(chr(10))


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers", {"env": env, "probe_ollama": probe_ollama})
    return [
        {"provider": p, "available": True, "reason": None,
         "suggested_model": cfg["suggested_model"], "api_key_env": cfg["default_api_key_env"]}
        for p, cfg in PROVIDERS.items()
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection", {"provider": provider, "model": model})
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + provider)
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config", {"config_path": str(config_path), "provider": provider, "model": model})
    data = {"provider": provider, "model": model, "base_url": base_url,
            "api_key_env": api_key_env, "timeout_seconds": timeout_seconds}
    existing = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                existing = json.load(f)
        except Exception:
            existing = {}
    existing["llm"] = data
    with open(config_path, "w") as f:
        json.dump(existing, f)


def load_config(config_path=None):
    _log("load_config", {"config_path": str(config_path) if config_path else None})
    if config_path is None or not os.path.exists(config_path):
        return None
    with open(config_path, "r") as f:
        try:
            existing = json.load(f)
        except Exception:
            return None
    return existing.get("llm")
''')


def _make_tool_root(base_dir, requirements_lines, log_path):
    tool_root = base_dir / "tool_root"
    tool_root.mkdir(parents=True, exist_ok=True)

    (tool_root / "requirements.txt").write_text("\n".join(requirements_lines) + "\n")

    llm_endpoint_dir = tool_root / "gen" / "llm-endpoint"
    llm_endpoint_dir.mkdir(parents=True, exist_ok=True)
    source = _LLM_ENDPOINT_TEMPLATE.replace("__LOG_PATH__", repr(str(log_path)))
    (llm_endpoint_dir / "llm_endpoint.py").write_text(source)

    compiler_dir = tool_root / "pipeline" / "criterion-compiler"
    compiler_dir.mkdir(parents=True, exist_ok=True)
    (compiler_dir / "criterion_compiler.py").write_text(
        "# stub criterion-compiler, vendored only, never imported by this test\n"
    )

    slugify_dir = tool_root / "examples" / "slugify" / "specs" / "product"
    slugify_dir.mkdir(parents=True, exist_ok=True)
    (slugify_dir / "slugs.md").write_text("# slugify example spec stub\n")

    return tool_root


def _make_path_env(tmp_path, name, include_claude):
    path_dir = tmp_path / name
    path_dir.mkdir(parents=True, exist_ok=True)
    if include_claude:
        claude_path = path_dir / "claude"
        claude_path.write_text("#!/bin/sh\necho claude\n")
        mode = claude_path.stat().st_mode
        claude_path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return {"PATH": str(path_dir)}


def _assert_consecutive(lines, first, second):
    assert first in lines, "expected %r in output lines: %r" % (first, lines)
    idx = lines.index(first)
    assert idx + 1 < len(lines), "expected a line after %r" % (first,)
    assert lines[idx + 1] == second, "expected %r right after %r, got %r" % (
        second, first, lines[idx + 1])


def test_missing_requirements_package_returns_3_and_reports_fix_no_command_run(tmp_path):
    log_path = tmp_path / "calls1.log"
    tool_root = _make_tool_root(
        tmp_path,
        ["pytest==9.2.0", "no-such-pkg-xyz==1.0"],
        log_path,
    )
    tool_root_str = str(tool_root)
    project_dir = tmp_path / "project1"
    env = _make_path_env(tmp_path, "path1", include_claude=False)

    output_lines = []
    argv = [
        str(project_dir),
        "--provider", "ollama",
        "--model", "llama3.1:8b",
        "--no-test",
        "--yes",
    ]

    with mock.patch("subprocess.run", side_effect=AssertionError("no command should run")), \
         mock.patch("subprocess.Popen", side_effect=AssertionError("no command should run")), \
         mock.patch("subprocess.call", side_effect=AssertionError("no command should run")), \
         mock.patch("subprocess.check_call", side_effect=AssertionError("no command should run")), \
         mock.patch("subprocess.check_output", side_effect=AssertionError("no command should run")), \
         mock.patch("os.system", side_effect=AssertionError("no command should run")):
        rc = hotdocs_init.main(
            argv,
            tool_root=tool_root_str,
            input_fn=lambda prompt: "y",
            output_fn=output_lines.append,
            env=env,
        )

    assert rc == 3

    fix_line = "  fix: pip install -r " + tool_root_str + "/requirements.txt"
    _assert_consecutive(output_lines, "missing: no-such-pkg-xyz==1.0", fix_line)

    assert "missing: pytest==9.2.0" not in output_lines

    assert project_dir.exists()
    assert (project_dir / "gen" / "llm-endpoint" / "llm_endpoint.py").exists()
    assert (project_dir / "pipeline" / "criterion-compiler" / "criterion_compiler.py").exists()


def test_claude_cli_missing_on_path_returns_3_with_consecutive_lines(tmp_path):
    installed_version = importlib.metadata.version("pytest")
    log_path = tmp_path / "calls2a.log"
    tool_root = _make_tool_root(
        tmp_path,
        ["pytest==" + installed_version],
        log_path,
    )
    project_dir = tmp_path / "project2a"
    env = _make_path_env(tmp_path, "path2a", include_claude=False)

    output_lines = []
    argv = [
        str(project_dir),
        "--provider", "claude-cli",
        "--model", "claude-sonnet-5",
        "--no-test",
        "--yes",
    ]
    rc = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=lambda prompt: "y",
        output_fn=output_lines.append,
        env=env,
    )

    assert rc == 3
    _assert_consecutive(
        output_lines, "missing: claude on PATH", "  fix: install Claude Code and sign in"
    )


def test_claude_cli_present_on_path_returns_0(tmp_path):
    installed_version = importlib.metadata.version("pytest")
    log_path = tmp_path / "calls2b.log"
    tool_root = _make_tool_root(
        tmp_path,
        ["pytest==" + installed_version],
        log_path,
    )
    project_dir = tmp_path / "project2b"
    env = _make_path_env(tmp_path, "path2b", include_claude=True)

    output_lines = []
    argv = [
        str(project_dir),
        "--provider", "claude-cli",
        "--model", "claude-sonnet-5",
        "--no-test",
        "--yes",
    ]
    rc = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=lambda prompt: "y",
        output_fn=output_lines.append,
        env=env,
    )

    assert rc == 0


def test_provider_ollama_no_claude_on_path_returns_0(tmp_path):
    installed_version = importlib.metadata.version("pytest")
    log_path = tmp_path / "calls2c.log"
    tool_root = _make_tool_root(
        tmp_path,
        ["pytest==" + installed_version],
        log_path,
    )
    project_dir = tmp_path / "project2c"
    env = _make_path_env(tmp_path, "path2c", include_claude=False)

    output_lines = []
    argv = [
        str(project_dir),
        "--provider", "ollama",
        "--model", "llama3.1:8b",
        "--no-test",
        "--yes",
    ]
    rc = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=lambda prompt: "y",
        output_fn=output_lines.append,
        env=env,
    )

    assert rc == 0