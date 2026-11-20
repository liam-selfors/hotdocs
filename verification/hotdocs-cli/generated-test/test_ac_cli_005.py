# hotdocs-criterion: sha256:4360fb4f43c01dd1db087f5c6dde5af1ba792fbb622909fa01dbf47835ad1e15
import builtins
import json
import os
from pathlib import Path

import hotdocs_cli


def _fake_source(log_path):
    return (
        "import builtins\n"
        "import json\n"
        "import os\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def run(argv, **keywords):\n"
        "    record = {}\n"
        "    record['argv'] = list(argv)\n"
        "    record['keys'] = sorted(keywords.keys())\n"
        "    tr = keywords.get('tool_root')\n"
        "    record['tool_root'] = None if tr is None else os.fspath(tr)\n"
        "    cw = keywords.get('cwd')\n"
        "    record['cwd'] = None if cw is None else os.fspath(cw)\n"
        "    record['input_fn_id'] = id(keywords.get('input_fn'))\n"
        "    record['output_fn_id'] = id(keywords.get('output_fn'))\n"
        "    record['env_id'] = id(keywords.get('env'))\n"
        "    record['input_is_builtin'] = keywords.get('input_fn') is builtins.input\n"
        "    record['output_is_builtin'] = keywords.get('output_fn') is builtins.print\n"
        "    env = keywords.get('env')\n"
        "    record['env_is_os_environ'] = env is os.environ\n"
        "    try:\n"
        "        record['env_equals_os_environ'] = dict(env) == dict(os.environ)\n"
        "    except Exception:\n"
        "        record['env_equals_os_environ'] = False\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
        "    return 7\n"
    )


def _make_tool_root(tmp_path, log_path):
    tool_root = tmp_path / "toolroot"
    fake_dir = tool_root / "gen" / "hotdocs-init"
    fake_dir.mkdir(parents=True)
    (fake_dir / "hotdocs_init.py").write_text(_fake_source(log_path), encoding="utf-8")
    return tool_root


def _read_log(log_path):
    assert log_path.is_file(), "fake hotdocs_init.run was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def _same_path(a, b):
    return os.path.realpath(os.fspath(a)) == os.path.realpath(os.fspath(b))


def test_init_forwards_exact_keywords_and_tokens(tmp_path):
    log_path = tmp_path / "calls.log"
    tool_root = _make_tool_root(tmp_path, log_path)
    project = tmp_path / "project"
    project.mkdir()
    assert not (project / "gen").exists()

    def f(prompt=""):
        return ""

    def g(*args, **kwargs):
        return None

    e = {"HOTDOCS_TEST_ENV": "1"}

    code = hotdocs_cli.run(
        ["init", "dir", "--yes"],
        tool_root=str(tool_root),
        input_fn=f,
        output_fn=g,
        env=e,
        cwd=str(project),
    )

    records = _read_log(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["argv"] == ["dir", "--yes"]
    assert not any(tok.startswith("--repo-root") for tok in rec["argv"])
    assert rec["keys"] == sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])
    assert _same_path(rec["tool_root"], tool_root)
    assert _same_path(rec["cwd"], project)
    assert rec["input_fn_id"] == id(f)
    assert rec["output_fn_id"] == id(g)
    assert rec["env_id"] == id(e)
    assert code == 7


def test_init_defaults_filled_in(tmp_path, monkeypatch):
    log_path = tmp_path / "calls.log"
    tool_root = _make_tool_root(tmp_path, log_path)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    # tool_root is supplied only so the fake can be located; input_fn,
    # output_fn, env and cwd are left to their defaults.
    code = hotdocs_cli.run(["init"], tool_root=str(tool_root))

    records = _read_log(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["argv"] == []
    assert rec["keys"] == sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])
    assert rec["input_is_builtin"] is True
    assert rec["input_fn_id"] == id(builtins.input)
    assert rec["output_is_builtin"] is True
    assert rec["output_fn_id"] == id(builtins.print)
    assert rec["env_is_os_environ"] or rec["env_equals_os_environ"]
    assert rec["cwd"] is not None
    assert _same_path(rec["cwd"], project)
    assert _same_path(rec["cwd"], Path(os.getcwd()))
    assert code == 7