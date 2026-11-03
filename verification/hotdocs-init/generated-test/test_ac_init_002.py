import json
import os
from pathlib import Path

import pytest

import hotdocs_init


LLM_ENDPOINT_TEMPLATE = '''import json
import os

LOG_PATH = __LOG_PATH__


def _log(name, **kwargs):
    entry = {"name": name}
    entry.update(kwargs)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\\n")


PROVIDERS = {
    "anthropic": {
        "default_base_url": None,
        "default_api_key_env": "ANTHROPIC_API_KEY",
        "needs_base_url": False,
        "suggested_model": "claude-sonnet-5",
    },
}


def detect_providers(env=None, probe_ollama=True):
    _log("detect_providers")
    return [
        {
            "provider": "anthropic",
            "available": True,
            "reason": "fake",
            "suggested_model": "claude-sonnet-5",
            "api_key_env": "ANTHROPIC_API_KEY",
        }
    ]


def check_connection(provider, model, base_url=None, api_key_env=None, timeout_seconds=30):
    _log("check_connection")
    return {"ok": True, "error": None}


def save_config(config_path, provider, model, base_url=None, api_key_env=None, timeout_seconds=None):
    _log("save_config")
    existing = ""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            existing = f.read()
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(existing)
        f.write("\\n[llm]\\n")
        f.write("provider = \\"" + provider + "\\"\\n")
        f.write("model = \\"" + model + "\\"\\n")


def load_config(config_path=None):
    _log("load_config")
    return None
'''


def _write_tool_root(root: Path, log_path: Path) -> None:
    (root / "gen" / "a-b").mkdir(parents=True)
    (root / "gen" / "a-b" / "a_b.py").write_text(
        "A_B_MARKER = 'a-b-module-source'\n", encoding="utf-8"
    )

    (root / "gen" / "c" / "__pycache__").mkdir(parents=True)
    (root / "gen" / "c" / "__pycache__" / "x.pyc").write_bytes(b"\x00fake-stale-bytecode")

    llm_dir = root / "gen" / "llm-endpoint"
    llm_dir.mkdir(parents=True)
    source = LLM_ENDPOINT_TEMPLATE.replace("__LOG_PATH__", json.dumps(str(log_path)))
    (llm_dir / "llm_endpoint.py").write_text(source, encoding="utf-8")

    pipeline_dir = root / "pipeline" / "criterion-compiler"
    pipeline_dir.mkdir(parents=True)
    (pipeline_dir / "criterion_compiler.py").write_text(
        "CRITERION_COMPILER_MARKER = 'criterion-compiler-source'\n", encoding="utf-8"
    )


def _assert_no_pycache(root: Path) -> None:
    for dirpath, dirnames, _filenames in os.walk(root):
        assert "__pycache__" not in dirnames, "found __pycache__ under {}".format(dirpath)


def test_init_vendors_tool_and_skips_on_second_run(tmp_path):
    tool_root = tmp_path / "tool_root"
    tool_root.mkdir()
    log_path = tmp_path / "llm_endpoint_calls.log"
    _write_tool_root(tool_root, log_path)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    messages = []

    def output_fn(msg):
        messages.append(str(msg))

    def input_fn(prompt=""):
        return ""

    argv = [
        str(project_dir),
        "--provider", "anthropic",
        "--model", "claude-sonnet-5",
        "--no-test",
        "--yes",
    ]

    rc = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
        cwd=str(project_dir),
    )

    assert rc == 0

    copied_a_b = project_dir / "gen" / "a-b" / "a_b.py"
    copied_cc = project_dir / "pipeline" / "criterion-compiler" / "criterion_compiler.py"

    assert copied_a_b.exists()
    assert not copied_a_b.is_symlink()
    assert copied_a_b.read_text(encoding="utf-8") == (
        tool_root / "gen" / "a-b" / "a_b.py"
    ).read_text(encoding="utf-8")

    assert copied_cc.exists()
    assert not copied_cc.is_symlink()
    assert copied_cc.read_text(encoding="utf-8") == (
        tool_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py"
    ).read_text(encoding="utf-8")

    _assert_no_pycache(project_dir)

    assert log_path.exists()
    log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) >= 1

    stamp_path = project_dir / ".hotdocs-tool.json"
    assert stamp_path.exists()
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))

    assert stamp["tool_version"] == "0.1.0"
    assert stamp["vendored"] == sorted(stamp["vendored"])
    assert stamp["vendored"] == [
        "gen/a-b",
        "gen/c",
        "gen/llm-endpoint",
        "pipeline/criterion-compiler",
    ]
    assert isinstance(stamp["content_hash"], str)
    assert stamp["content_hash"].startswith("sha256:")

    first_stamp_bytes = stamp_path.read_bytes()
    first_a_b_mtime_ns = copied_a_b.stat().st_mtime_ns
    first_cc_mtime_ns = copied_cc.stat().st_mtime_ns

    messages.clear()

    rc2 = hotdocs_init.main(
        argv,
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=output_fn,
        env={},
        cwd=str(project_dir),
    )

    assert rc2 == 0

    joined_messages = "\n".join(messages)
    for vendored_path in stamp["vendored"]:
        assert vendored_path in joined_messages
    assert "skip" in joined_messages.lower()

    assert stamp_path.read_bytes() == first_stamp_bytes
    assert copied_a_b.stat().st_mtime_ns == first_a_b_mtime_ns
    assert copied_cc.stat().st_mtime_ns == first_cc_mtime_ns

    _assert_no_pycache(project_dir)


def test_init_refuses_when_target_has_untracked_vendor_path(tmp_path, capsys):
    tool_root = tmp_path / "tool_root_b"
    tool_root.mkdir()
    log_path = tmp_path / "llm_endpoint_calls_b.log"
    _write_tool_root(tool_root, log_path)

    project_dir = tmp_path / "project_b"
    project_dir.mkdir()
    existing = project_dir / "gen" / "a-b"
    existing.mkdir(parents=True)
    marker = existing / "preexisting.txt"
    marker.write_text("do not touch\n", encoding="utf-8")

    before_listing = sorted(str(p.relative_to(project_dir)) for p in project_dir.rglob("*"))

    def input_fn(prompt=""):
        return ""

    rc = hotdocs_init.main(
        [str(project_dir)],
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=lambda msg: None,
        env={},
        cwd=str(project_dir),
    )

    captured = capsys.readouterr()

    assert rc == 1
    assert "gen/a-b" in captured.err

    after_listing = sorted(str(p.relative_to(project_dir)) for p in project_dir.rglob("*"))
    assert before_listing == after_listing
    assert marker.read_text(encoding="utf-8") == "do not touch\n"
    assert not (project_dir / ".hotdocs-tool.json").exists()


def test_init_refuses_when_target_is_tool_root_itself(tmp_path, capsys):
    tool_root = tmp_path / "tool_root_c"
    tool_root.mkdir()
    log_path = tmp_path / "llm_endpoint_calls_c.log"
    _write_tool_root(tool_root, log_path)

    def snapshot():
        contents = {}
        for p in sorted(tool_root.rglob("*")):
            if p.is_file():
                contents[str(p.relative_to(tool_root))] = p.read_bytes()
        return contents

    before = snapshot()

    def input_fn(prompt=""):
        return ""

    rc = hotdocs_init.main(
        [str(tool_root)],
        tool_root=str(tool_root),
        input_fn=input_fn,
        output_fn=lambda msg: None,
        env={},
        cwd=str(tool_root),
    )

    assert rc == 1

    after = snapshot()
    assert before == after
    assert not (tool_root / ".hotdocs-tool.json").exists()