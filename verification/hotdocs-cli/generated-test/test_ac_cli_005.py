# hotdocs-criterion: sha256:40643a37a3aff1121445c34cdc2f45330750f39bf8853e9418ff07d5d7260ed8
import json
import os

import hotdocs_cli


def _write_fake_init(tool_root, log_path):
    target = tool_root / "gen" / "hotdocs-init" / "hotdocs_init.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "import builtins\n"
        "import json\n"
        "import os\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def run(argv, **keywords):\n"
        "    env = keywords.get('env')\n"
        "    env_is_os = env is os.environ\n"
        "    try:\n"
        "        env_equals_os = env is not None and dict(env) == dict(os.environ)\n"
        "    except Exception:\n"
        "        env_equals_os = False\n"
        "    env_copy = None\n"
        "    if env is not None and not env_is_os and not env_equals_os:\n"
        "        env_copy = dict(env)\n"
        "    rec = {\n"
        "        'argv': list(argv),\n"
        "        'keys': sorted(keywords),\n"
        "        'ids': dict((k, id(v)) for k, v in keywords.items()),\n"
        "        'tool_root': None if keywords.get('tool_root') is None else str(keywords.get('tool_root')),\n"
        "        'cwd': None if keywords.get('cwd') is None else str(keywords.get('cwd')),\n"
        "        'env_is_os_environ': env_is_os,\n"
        "        'env_equals_os_environ': env_equals_os,\n"
        "        'env': env_copy,\n"
        "        'input_is_input': keywords.get('input_fn') is builtins.input,\n"
        "        'output_is_print': keywords.get('output_fn') is builtins.print,\n"
        "    }\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(rec) + '\\n')\n"
        "    return 7\n"
    )
    target.write_text(source, encoding="utf-8")


def _read_log(log_path):
    assert log_path.is_file(), "fake init run was never called"
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1, lines
    return json.loads(lines[0])


def _same_path(a, b):
    return os.path.abspath(str(a)) == os.path.abspath(str(b))


def test_init_calls_run_with_exact_keywords(tmp_path):
    tool_root = tmp_path / "toolroot"
    project = tmp_path / "project"
    project.mkdir()
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    _write_fake_init(tool_root, log_path)
    assert not (project / "gen").exists()

    def f(prompt=""):
        return ""

    def g(*args, **kwargs):
        return None

    e = {"HOTDOCS_AC_CLI_005_MARK": "marker-value"}

    rc = hotdocs_cli.run(
        ["init", "dir", "--yes"],
        tool_root=tool_root,
        input_fn=f,
        output_fn=g,
        env=e,
        cwd=project,
    )

    assert rc == 7
    rec = _read_log(log_path)
    assert rec["argv"] == ["dir", "--yes"]
    assert not any(t.startswith("--repo-root") for t in rec["argv"])
    assert rec["keys"] == sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])
    assert rec["ids"]["input_fn"] == id(f)
    assert rec["ids"]["output_fn"] == id(g)
    assert rec["ids"]["env"] == id(e) or rec["env"] == e
    assert _same_path(rec["tool_root"], tool_root)
    assert _same_path(rec["cwd"], project)


def test_init_defaults_filled_in(tmp_path, monkeypatch):
    tool_root = tmp_path / "toolroot"
    project = tmp_path / "project"
    project.mkdir()
    log_path = tmp_path / "logs" / "calls.log"
    log_path.parent.mkdir()
    _write_fake_init(tool_root, log_path)
    monkeypatch.chdir(project)

    # tool_root is supplied only so the fake can be found without touching the
    # real tool; input_fn, output_fn, env and cwd are all left to their defaults.
    rc = hotdocs_cli.run(["init"], tool_root=tool_root)

    assert rc == 7
    rec = _read_log(log_path)
    assert rec["argv"] == []
    assert rec["keys"] == sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])
    assert rec["input_is_input"] is True
    assert rec["output_is_print"] is True
    assert rec["env_is_os_environ"] or rec["env_equals_os_environ"]
    assert rec["cwd"] is not None
    assert _same_path(rec["cwd"], os.getcwd())
    assert _same_path(rec["tool_root"], tool_root)