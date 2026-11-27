# hotdocs-criterion: sha256:164ed8462048681e1dcd202c656e49e4f3a1b00ad0c611c72db7492152370998
import json
import os

import hotdocs_cli


FAKE_TEMPLATE_HEAD = (
    "import builtins\n"
    "import json\n"
    "import os\n"
    "\n"
)

FAKE_TEMPLATE_BODY = (
    "\n"
    "def run(argv, **keywords):\n"
    "    info = {}\n"
    "    for k, v in keywords.items():\n"
    "        d = {\n"
    "            'id': id(v),\n"
    "            'is_input': v is builtins.input,\n"
    "            'is_print': v is builtins.print,\n"
    "            'is_environ': v is os.environ,\n"
    "        }\n"
    "        try:\n"
    "            d['fspath'] = os.fspath(v)\n"
    "        except TypeError:\n"
    "            d['fspath'] = None\n"
    "        try:\n"
    "            d['mapping'] = {str(a): str(b) for a, b in dict(v).items()}\n"
    "        except Exception:\n"
    "            d['mapping'] = None\n"
    "        info[k] = d\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'argv': list(argv), 'keywords': info}) + '\\n')\n"
    "    return 7\n"
)


def _make_tool_root(tmp_path):
    tool_root = tmp_path / "toolroot"
    fake_dir = tool_root / "gen" / "hotdocs-init"
    fake_dir.mkdir(parents=True)
    log_path = tool_root / "calls.log"
    source = FAKE_TEMPLATE_HEAD + "LOG = " + repr(str(log_path)) + "\n" + FAKE_TEMPLATE_BODY
    (fake_dir / "hotdocs_init.py").write_text(source, encoding="utf-8")
    return tool_root, log_path


def _read_calls(log_path):
    assert log_path.is_file(), "the fake hotdocs_init.run was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_init_run_receives_given_keywords(tmp_path):
    tool_root, log_path = _make_tool_root(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    assert not (project / "gen").exists()

    def f(prompt=""):
        return ""

    def g(*args, **kwargs):
        return None

    e = {"HOTDOCS_TEST_MARKER": "abc", "PATH": os.environ.get("PATH", "")}
    c = str(project)

    rc = hotdocs_cli.run(
        ["init", "dir", "--yes"],
        tool_root=str(tool_root),
        input_fn=f,
        output_fn=g,
        env=e,
        cwd=c,
    )

    calls = _read_calls(log_path)
    assert len(calls) == 1
    call = calls[0]
    assert call["argv"] == ["dir", "--yes"]
    assert not any(str(tok).startswith("--repo-root") for tok in call["argv"])

    kws = call["keywords"]
    assert set(kws) == {"tool_root", "input_fn", "output_fn", "env", "cwd"}

    assert kws["tool_root"]["fspath"] is not None
    assert os.path.abspath(kws["tool_root"]["fspath"]) == os.path.abspath(str(tool_root))
    assert kws["input_fn"]["id"] == id(f)
    assert kws["output_fn"]["id"] == id(g)
    assert kws["env"]["id"] == id(e) or kws["env"]["mapping"] == e
    assert kws["cwd"]["fspath"] is not None
    assert os.path.abspath(kws["cwd"]["fspath"]) == os.path.abspath(c)

    assert rc == 7


def test_init_run_receives_defaults(tmp_path, monkeypatch):
    tool_root, log_path = _make_tool_root(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOTDOCS_TEST_MARKER", "default-env")

    rc = hotdocs_cli.run(["init"], tool_root=str(tool_root))

    calls = _read_calls(log_path)
    assert len(calls) == 1
    call = calls[0]
    assert call["argv"] == []

    kws = call["keywords"]
    assert set(kws) == {"tool_root", "input_fn", "output_fn", "env", "cwd"}
    assert kws["input_fn"]["is_input"] is True
    assert kws["output_fn"]["is_print"] is True
    env_info = kws["env"]
    assert env_info["is_environ"] is True or env_info["mapping"] == {
        str(k): str(v) for k, v in os.environ.items()
    }
    assert kws["cwd"]["fspath"] is not None
    assert os.path.realpath(kws["cwd"]["fspath"]) == os.path.realpath(os.getcwd())
    assert os.path.realpath(kws["cwd"]["fspath"]) == os.path.realpath(str(project))

    assert rc == 7