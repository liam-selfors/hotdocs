"""AC-CLI-005: the `init` row loads from the tool root and forwards keywords."""

import builtins
import json
import os
import sys
from pathlib import Path

import pytest

import hotdocs_cli


EXPECTED_KEYS = {"tool_root", "input_fn", "output_fn", "env", "cwd"}


def _write_fake_init(tool_root: Path, log_path: Path) -> None:
    fake_dir = tool_root / "gen" / "hotdocs-init"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = f'''
import json
import os

_LOG = {str(log_path)!r}


def main(argv, **kwargs):
    env = kwargs.get("env")
    try:
        env_dict = dict(env) if env is not None else None
    except Exception:
        env_dict = None
    tool_root = kwargs.get("tool_root")
    cwd = kwargs.get("cwd")
    record = {{
        "argv": list(argv) if argv is not None else None,
        "keys": sorted(kwargs.keys()),
        "ids": {{k: id(v) for k, v in kwargs.items()}},
        "tool_root": None if tool_root is None else str(tool_root),
        "cwd": None if cwd is None else str(cwd),
        "env": env_dict,
        "env_is_os_environ": env is os.environ,
    }}
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")
    return 7
'''
    (fake_dir / "hotdocs_init.py").write_text(source, encoding="utf-8")


def _read_log(log_path: Path):
    assert log_path.exists(), "fake init main was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _same_path(a, b) -> bool:
    return os.path.realpath(str(a)) == os.path.realpath(str(b))


@pytest.fixture
def layout(tmp_path, monkeypatch):
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    log_path = tmp_path / "init_calls.log"
    _write_fake_init(tool_root, log_path)
    monkeypatch.delitem(sys.modules, "hotdocs_init", raising=False)
    monkeypatch.chdir(project)
    assert not (project / "gen").exists()
    return tool_root, project, log_path


def test_init_receives_tokens_and_given_keywords(layout):
    tool_root, project, log_path = layout

    def f(prompt=""):
        return ""

    def g(*args, **kwargs):
        return None

    e = {"HOTDOCS_TEST_MARKER": "1"}
    c = project

    rc = hotdocs_cli.main(
        ["init", "dir", "--yes"],
        tool_root=tool_root,
        input_fn=f,
        output_fn=g,
        env=e,
        cwd=c,
    )

    assert rc == 7

    records = _read_log(log_path)
    assert len(records) == 1
    rec = records[0]

    assert rec["argv"] == ["dir", "--yes"]
    assert "--repo-root" not in rec["argv"]
    assert set(rec["keys"]) == EXPECTED_KEYS
    assert len(rec["keys"]) == len(EXPECTED_KEYS)

    assert rec["ids"]["input_fn"] == id(f)
    assert rec["ids"]["output_fn"] == id(g)
    assert rec["env"] == e
    assert _same_path(rec["tool_root"], tool_root)
    assert _same_path(rec["cwd"], c)


def test_init_defaults_filled_in(layout):
    tool_root, project, log_path = layout

    rc = hotdocs_cli.main(["init"], tool_root=tool_root)

    assert rc == 7

    records = _read_log(log_path)
    assert len(records) == 1
    rec = records[0]

    assert rec["argv"] == []
    assert "--repo-root" not in rec["argv"]
    assert set(rec["keys"]) == EXPECTED_KEYS

    assert rec["ids"]["input_fn"] == id(builtins.input)
    assert rec["ids"]["output_fn"] == id(builtins.print)
    assert rec["env_is_os_environ"] or rec["env"] == dict(os.environ)
    assert rec["env"] is not None
    assert _same_path(rec["cwd"], os.getcwd())
    assert _same_path(rec["cwd"], project)
    assert _same_path(rec["tool_root"], tool_root)