import os
import importlib.metadata
from unittest import mock

import hotdocs_init


FAKE_LLM_ENDPOINT_SRC = r'''
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
    return [
        {
            "provider": "claude-cli",
            "available": True,
            "reason": None,
            "suggested_model": "claude-sonnet-5",
            "api_key_env": None,
        },
        {
            "provider": "ollama",
            "available": True,
            "reason": None,
            "suggested_model": "llama3.1:8b",
            "api_key_env": None,
        },
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    if provider not in PROVIDERS:
        raise ValueError("unknown provider: " + str(provider))
    if PROVIDERS[provider]["needs_base_url"] and not base_url:
        raise ValueError("base_url required for " + str(provider))
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    lines = ["[llm]", 'provider = "' + provider + '"', 'model = "' + model + '"']
    if base_url is not None:
        lines.append('base_url = "' + base_url + '"')
    if api_key_env is not None:
        lines.append('api_key_env = "' + api_key_env + '"')
    if timeout_seconds is not None:
        lines.append("timeout_seconds = " + str(timeout_seconds))
    with open(config_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def load_config(config_path=None):
    if config_path is None:
        return None
    import os
    if not os.path.exists(config_path):
        return None
    with open(config_path, "r") as f:
        text = f.read()
    if "[llm]" not in text:
        return None
    result = {
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "timeout_seconds": None,
    }
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("provider"):
            result["provider"] = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("model"):
            result["model"] = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("base_url"):
            result["base_url"] = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("api_key_env"):
            result["api_key_env"] = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("timeout_seconds"):
            result["timeout_seconds"] = int(line.split("=", 1)[1].strip())
    return result
'''


def _make_tool_root(tmp_path, requirements_text):
    tool_root_dir = tmp_path / "tool_root"
    (tool_root_dir / "gen" / "llm-endpoint").mkdir(parents=True)
    (tool_root_dir / "gen" / "llm-endpoint" / "llm_endpoint.py").write_text(FAKE_LLM_ENDPOINT_SRC)
    (tool_root_dir / "requirements.txt").write_text(requirements_text)
    return str(tool_root_dir)


def test_missing_requirement_reports_and_returns_3(tmp_path):
    tool_root = _make_tool_root(tmp_path, "pytest==9.2.0\nno-such-pkg-xyz==1.0\n")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    lines = []
    # subprocess.run/call/check_call/check_output all dispatch through Popen
    # internally, so patching Popen alone catches any command execution
    # regardless of which wrapper (or import style) the target code uses.
    with mock.patch("subprocess.Popen") as popen_mock:
        rc = hotdocs_init.main(
            [str(project_dir), "--provider=ollama", "--model=llama3.1:8b", "--yes"],
            tool_root=tool_root,
            output_fn=lambda *a, **k: lines.append(a[0] if a else ""),
            env={"PATH": os.environ.get("PATH", "")},
            cwd=str(project_dir),
        )
        assert popen_mock.call_count == 0

    assert rc == 3

    fix_line = "  fix: pip install -r " + tool_root + "/requirements.txt"
    assert any(
        lines[i] == "missing: no-such-pkg-xyz==1.0" and lines[i + 1] == fix_line
        for i in range(len(lines) - 1)
    ), lines
    assert "missing: pytest==9.2.0" not in lines


def test_claude_on_path_prerequisite(tmp_path):
    pytest_version = importlib.metadata.version("pytest")
    tool_root = _make_tool_root(tmp_path, "pytest==" + pytest_version + "\n")

    empty_bin = tmp_path / "empty_bin"
    empty_bin.mkdir()

    project_a = tmp_path / "proj_a"
    project_a.mkdir()
    lines_a = []
    rc_a = hotdocs_init.main(
        [str(project_a), "--provider=claude-cli", "--model=claude-sonnet-5", "--yes"],
        tool_root=tool_root,
        output_fn=lambda *a, **k: lines_a.append(a[0] if a else ""),
        env={"PATH": str(empty_bin)},
        cwd=str(project_a),
    )
    assert rc_a == 3
    assert any(
        lines_a[i] == "missing: claude on PATH"
        and lines_a[i + 1] == "  fix: install Claude Code and sign in"
        for i in range(len(lines_a) - 1)
    ), lines_a

    bin_with_claude = tmp_path / "bin_with_claude"
    bin_with_claude.mkdir()
    claude_path = bin_with_claude / "claude"
    claude_path.write_text("#!/bin/sh\necho claude-stub\n")
    os.chmod(claude_path, 0o755)

    project_b = tmp_path / "proj_b"
    project_b.mkdir()
    lines_b = []
    rc_b = hotdocs_init.main(
        [str(project_b), "--provider=claude-cli", "--model=claude-sonnet-5", "--yes"],
        tool_root=tool_root,
        output_fn=lambda *a, **k: lines_b.append(a[0] if a else ""),
        env={"PATH": str(bin_with_claude)},
        cwd=str(project_b),
    )
    assert rc_b == 0

    project_c = tmp_path / "proj_c"
    project_c.mkdir()
    lines_c = []
    rc_c = hotdocs_init.main(
        [str(project_c), "--provider=ollama", "--model=llama3.1:8b", "--yes"],
        tool_root=tool_root,
        output_fn=lambda *a, **k: lines_c.append(a[0] if a else ""),
        env={"PATH": str(empty_bin)},
        cwd=str(project_c),
    )
    assert rc_c == 0