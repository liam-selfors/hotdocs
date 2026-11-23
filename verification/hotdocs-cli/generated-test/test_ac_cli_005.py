# hotdocs-criterion: sha256:ce113e7fc004a4157b4cd32717175ee744a17d814c8b31ad664eeb78d540a5a4
import builtins
import json
import os
from pathlib import Path

import hotdocs_cli


def _write_fake_init(tool_root, log_path):
    target = Path(tool_root) / "gen" / "hotdocs-init"
    target.mkdir(parents=True, exist_ok=True)
    source = (
        "import builtins\n"
        "import json\n"
        "import os\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def run(argv, **keywords):\n"
        "    env = keywords.get('env')\n"
        "    try:\n"
        "        env_equal = dict(env) == dict(os.environ)\n"
        "    except Exception:\n"
        "        env_equal = False\n"
        "    record = {\n"
        "        'argv': list(argv) if argv is not None else None,\n"
        "        'keys': sorted(keywords.keys()),\n"
        "        'ids': dict((k, id(v)) for k, v in keywords.items()),\n"
        "        'tool_root': None if keywords.get('tool_root') is None else os.fspath(keywords.get('tool_root')),\n"
        "        'cwd': None if keywords.get('cwd') is None else os.fspath(keywords.get('cwd')),\n"
        "        'env_dict': dict(env) if env is not None else None,\n"
        "        'input_is_builtin': keywords.get('input_fn') is builtins.input,\n"
        "        'print_is_builtin': keywords.get('output_fn') is builtins.print,\n"
        "        'env_is_environ': env is os.environ,\n"
        "        'env_equal_environ': env_equal,\n"
        "    }\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
        "    return 7\n"
    )
    (target / "hotdocs_init.py").write_text(source, encoding="utf-8")


def _read_log(log_path):
    lines = [l for l in Path(log_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


EXPECTED_KEYS = sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])


def test_init_forwards_tokens_and_keywords_from_tool_root(tmp_path):
    tool_root = tmp_path / "toolroot"
    tool_root.mkdir()
    logdir = tmp_path / "logs"
    logdir.mkdir()
    log_path = logdir / "calls.log"
    _write_fake_init(tool_root, log_path)

    project = tmp_path / "project"
    project.mkdir()
    assert not (project / "gen").exists()

    def f(prompt=""):
        return ""

    def g(*args, **kwargs):
        return None

    e = {"HOTDOCS_TEST_MARK": "ac-cli-005"}
    c = str(project)

    code = hotdocs_cli.run(
        ["init", "dir", "--yes"],
        tool_root=str(tool_root),
        input_fn=f,
        output_fn=g,
        env=e,
        cwd=c,
    )

    records = _read_log(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["argv"] == ["dir", "--yes"]
    assert not any(str(t).startswith("--repo-root") for t in rec["argv"])
    assert rec["keys"] == EXPECTED_KEYS
    assert rec["ids"]["input_fn"] == id(f)
    assert rec["ids"]["output_fn"] == id(g)
    assert rec["ids"]["env"] == id(e) or rec["env_dict"] == e
    assert Path(rec["tool_root"]) == Path(str(tool_root))
    assert Path(rec["cwd"]) == Path(c)
    assert code == 7


def test_init_defaults_filled_in(tmp_path, monkeypatch):
    tool_root = tmp_path / "toolroot2"
    tool_root.mkdir()
    logdir = tmp_path / "logs2"
    logdir.mkdir()
    log_path = logdir / "calls.log"
    _write_fake_init(tool_root, log_path)

    project = tmp_path / "project2"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOTDOCS_TEST_MARK", "defaults")

    code = hotdocs_cli.run(["init"], tool_root=str(tool_root))

    records = _read_log(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["argv"] == []
    assert rec["keys"] == EXPECTED_KEYS
    assert rec["input_is_builtin"] is True
    assert rec["print_is_builtin"] is True
    assert rec["env_is_environ"] or rec["env_equal_environ"]
    assert rec["env_dict"].get("HOTDOCS_TEST_MARK") == "defaults"
    assert rec["cwd"] is not None
    assert os.path.realpath(rec["cwd"]) == os.path.realpath(str(project))
    assert code == 7