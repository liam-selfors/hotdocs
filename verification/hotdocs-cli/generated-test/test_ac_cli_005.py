import builtins
import json
import os
from pathlib import Path

import pytest

import hotdocs_cli


FAKE_INIT_SOURCE = '''
import json

LOG_PATH = {log_path!r}


def main(argv=None, **kwargs):
    env = kwargs.get("env")
    record = {{
        "argv": list(argv) if argv is not None else None,
        "keys": sorted(kwargs.keys()),
        "ids": {{k: id(v) for k, v in kwargs.items()}},
        "strs": {{k: str(v) for k, v in kwargs.items() if k in ("tool_root", "cwd")}},
        "env": {{str(k): str(v) for k, v in dict(env).items()}} if env is not None else None,
    }}
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")
    return 7
'''


def _make_tool_root(tmp_path):
    tool_root = tmp_path / "toolroot"
    init_dir = tool_root / "gen" / "hotdocs-init"
    init_dir.mkdir(parents=True)
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir(parents=True)
    (init_dir / "hotdocs_init.py").write_text(
        FAKE_INIT_SOURCE.format(log_path=str(log_path)), encoding="utf-8"
    )
    return tool_root, log_path


def _make_empty_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    assert not (project / "gen").exists()
    return project


def _read_records(log_path):
    assert log_path.exists(), "fake init main was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def test_init_forwards_remaining_tokens_and_given_keywords(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    tool_root, log_path = _make_tool_root(tmp_path)
    project = _make_empty_project(tmp_path)

    def f(prompt=""):
        return "y"

    def g(*args, **kwargs):
        return None

    e = {"HOTDOCS_TEST_MARKER": "ac-cli-005", "PATH": os.environ.get("PATH", "")}
    c = project

    rc = hotdocs_cli.main(
        ["init", "dir", "--yes"],
        tool_root=tool_root,
        input_fn=f,
        output_fn=g,
        env=e,
        cwd=c,
    )

    records = _read_records(log_path)
    assert len(records) == 1
    rec = records[0]

    # Remaining tokens only; no --repo-root appended.
    assert rec["argv"] == ["dir", "--yes"]
    assert "--repo-root" not in rec["argv"]

    # Exactly these keywords.
    assert rec["keys"] == sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])

    # With those values.
    assert rec["ids"]["input_fn"] == id(f)
    assert rec["ids"]["output_fn"] == id(g)
    assert rec["ids"]["env"] == id(e) or rec["env"] == e
    assert _same_path(rec["strs"]["tool_root"], tool_root)
    assert _same_path(rec["strs"]["cwd"], c)

    # Return value is the exit code.
    assert rc == 7


def test_init_fills_default_keywords(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    tool_root, log_path = _make_tool_root(tmp_path)
    project = _make_empty_project(tmp_path)
    monkeypatch.chdir(project)

    # tool_root is given so the fake (rather than the real init) is loaded;
    # input_fn, output_fn, env and cwd are omitted and must be defaulted.
    rc = hotdocs_cli.main(["init"], tool_root=tool_root)

    records = _read_records(log_path)
    assert len(records) == 1
    rec = records[0]

    assert rec["argv"] == []
    assert "--repo-root" not in rec["argv"]
    assert rec["keys"] == sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])

    assert rec["ids"]["input_fn"] == id(builtins.input)
    assert rec["ids"]["output_fn"] == id(builtins.print)

    current_env = {str(k): str(v) for k, v in dict(os.environ).items()}
    assert rec["ids"]["env"] == id(os.environ) or rec["env"] == current_env

    assert _same_path(rec["strs"]["cwd"], Path.cwd())
    assert _same_path(rec["strs"]["cwd"], project)
    assert _same_path(rec["strs"]["tool_root"], tool_root)

    assert rc == 7