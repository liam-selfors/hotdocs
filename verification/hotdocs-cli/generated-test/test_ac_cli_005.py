import json
import os
from pathlib import Path

import hotdocs_cli


def _write_fake_init(tool_root: Path, log_path: Path) -> None:
    init_dir = tool_root / "gen" / "hotdocs-init"
    init_dir.mkdir(parents=True)

    template = '''
import json

LOG_PATH = __LOG_PATH__


def main(argv, **kwargs):
    record = {
        "argv": list(argv),
        "keys": sorted(kwargs.keys()),
        "tool_root": kwargs.get("tool_root"),
        "input_fn_id": id(kwargs.get("input_fn")),
        "output_fn_id": id(kwargs.get("output_fn")),
        "env": dict(kwargs.get("env")) if kwargs.get("env") is not None else None,
        "cwd": kwargs.get("cwd"),
    }
    with open(LOG_PATH, "a") as fh:
        fh.write(json.dumps(record) + "\\n")
    return 7
'''
    source = template.replace("__LOG_PATH__", repr(str(log_path)))
    (init_dir / "hotdocs_init.py").write_text(source)


def test_init_explicit_keywords_route_to_tool_root_fake(tmp_path):
    tool_root = tmp_path / "tool_root"
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    log_path = tmp_path / "calls.log"
    _write_fake_init(tool_root, log_path)

    def f(prompt=""):
        return "unused"

    def g(*args, **kwargs):
        return None

    env = {"CUSTOM_VAR": "value"}

    exit_code = hotdocs_cli.main(
        ["init", "dir", "--yes"],
        tool_root=str(tool_root),
        input_fn=f,
        output_fn=g,
        env=env,
        cwd=str(project_dir),
    )

    assert exit_code == 7

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])

    assert record["argv"] == ["dir", "--yes"]
    assert record["keys"] == sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])
    assert record["tool_root"] == str(tool_root)
    assert record["input_fn_id"] == id(f)
    assert record["output_fn_id"] == id(g)
    assert record["env"] == env
    assert record["cwd"] == str(project_dir)


def test_init_defaults_filled_in_when_keywords_omitted(tmp_path):
    tool_root = tmp_path / "tool_root"
    log_path = tmp_path / "calls.log"
    _write_fake_init(tool_root, log_path)

    exit_code = hotdocs_cli.main(["init"], tool_root=str(tool_root))

    assert exit_code == 7

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])

    assert record["argv"] == []
    assert record["keys"] == sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])
    assert record["input_fn_id"] == id(input)
    assert record["output_fn_id"] == id(print)
    assert record["env"] == dict(os.environ)
    assert record["cwd"] == os.getcwd()