# hotdocs-criterion: sha256:61b96f4bf97ad131ffe023d44365ed9d89d446893b241e1a9165df469857a10b
import builtins
import json
import os
from pathlib import Path

import hotdocs_cli


def _write_fake_init(tool_root):
    log_path = tool_root / "calls.log"
    fake_dir = tool_root / "gen" / "hotdocs-init"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "import os\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def main(argv, **kwargs):\n"
        "    env = kwargs.get('env')\n"
        "    rec = {\n"
        "        'argv': list(argv),\n"
        "        'keys': sorted(kwargs.keys()),\n"
        "        'ids': dict((k, id(v)) for k, v in kwargs.items()),\n"
        "        'tool_root': None if kwargs.get('tool_root') is None else str(kwargs.get('tool_root')),\n"
        "        'cwd': None if kwargs.get('cwd') is None else str(kwargs.get('cwd')),\n"
        "        'env': None if env is None else dict((str(k), str(v)) for k, v in dict(env).items()),\n"
        "        'process_var_config': os.environ.get('VAR_HOTDOCS_CONFIG'),\n"
        "    }\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(rec) + '\\n')\n"
        "    return 7\n"
    )
    (fake_dir / "hotdocs_init.py").write_text(source, encoding="utf-8")
    return log_path


def _read_log(log_path):
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


EXPECTED_KEYS = sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])


def test_init_loaded_from_tool_root_with_explicit_keywords(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log_path = _write_fake_init(tool_root)

    project = tmp_path / "project"
    project.mkdir()
    assert not (project / "gen").exists()

    def f(prompt=""):
        return ""

    def g(*args, **kwargs):
        return None

    e = {"HOTDOCS_TEST_MARK": "1"}
    c = project

    rc = hotdocs_cli.main(
        ["init", "dir", "--yes"],
        tool_root=tool_root,
        input_fn=f,
        output_fn=g,
        env=e,
        cwd=c,
    )

    assert log_path.is_file(), "fake init component in tool root was not called"
    records = _read_log(log_path)
    assert len(records) == 1
    rec = records[0]

    assert rec["argv"] == ["dir", "--yes"]
    assert "--repo-root" not in rec["argv"]
    assert rec["keys"] == EXPECTED_KEYS

    assert rec["ids"]["input_fn"] == id(f)
    assert rec["ids"]["output_fn"] == id(g)
    assert rec["ids"]["env"] == id(e) or rec["env"] == e
    assert rec["env"] == {"HOTDOCS_TEST_MARK": "1"}
    assert "VAR_HOTDOCS_CONFIG" not in e
    assert rec["process_var_config"] is None
    assert Path(rec["tool_root"]).resolve() == tool_root.resolve()
    assert Path(rec["cwd"]).resolve() == project.resolve()

    assert rc == 7


def test_init_defaults_filled_in(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    tool_root = tmp_path / "tool"
    tool_root.mkdir()
    log_path = _write_fake_init(tool_root)

    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    rc = hotdocs_cli.main(["init"], tool_root=tool_root)

    assert log_path.is_file(), "fake init component in tool root was not called"
    records = _read_log(log_path)
    assert len(records) == 1
    rec = records[0]

    assert rec["argv"] == []
    assert rec["keys"] == EXPECTED_KEYS

    assert rec["ids"]["input_fn"] == id(builtins.input)
    assert rec["ids"]["output_fn"] == id(builtins.print)
    expected_env = dict((str(k), str(v)) for k, v in os.environ.items())
    assert rec["ids"]["env"] == id(os.environ) or rec["env"] == expected_env
    assert rec["env"] == expected_env
    assert rec["cwd"] is not None
    assert Path(rec["cwd"]).resolve() == Path.cwd().resolve()
    assert Path(rec["tool_root"]).resolve() == tool_root.resolve()

    assert rc == 7