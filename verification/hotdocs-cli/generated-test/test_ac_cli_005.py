# hotdocs-criterion: sha256:cb92b23a124d0f96d0ca2ec8c3c0eaec481823012514286e63eb08a4b3d7fac1
import json
import os
from pathlib import Path

import hotdocs_cli


FAKE_BODY = (
    "import builtins\n"
    "import json\n"
    "import os\n"
    "\n"
    "def _desc(name, v):\n"
    "    if name in ('tool_root', 'cwd'):\n"
    "        return {'str': str(v), 'real': os.path.realpath(str(v))}\n"
    "    if name == 'env':\n"
    "        return {'items': dict(v), 'is_os_environ': v is os.environ}\n"
    "    if name in ('input_fn', 'output_fn'):\n"
    "        return {'is_input': v is builtins.input, 'is_print': v is builtins.print}\n"
    "    return repr(v)\n"
    "\n"
    "def run(argv, **keywords):\n"
    "    rec = {'argv': list(argv), 'keys': sorted(keywords),\n"
    "           'desc': dict((k, _desc(k, v)) for k, v in keywords.items()),\n"
    "           'var_hotdocs_config': os.environ.get('VAR_HOTDOCS_CONFIG')}\n"
    "    inp = keywords.get('input_fn')\n"
    "    out = keywords.get('output_fn')\n"
    "    if inp is not None and inp is not builtins.input:\n"
    "        rec['input_result'] = inp('prompt-from-fake')\n"
    "    if out is not None and out is not builtins.print:\n"
    "        out('message-from-fake')\n"
    "    with open(LOG, 'a') as fh:\n"
    "        fh.write(json.dumps(rec) + '\\n')\n"
    "    return 7\n"
)


def write_fake_init(tool_root, log_path):
    d = Path(tool_root) / "gen" / "hotdocs-init"
    d.mkdir(parents=True, exist_ok=True)
    source = "LOG = " + repr(str(log_path)) + "\n" + FAKE_BODY
    (d / "hotdocs_init.py").write_text(source)


def read_log(log_path):
    lines = [l for l in Path(log_path).read_text().splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


EXPECTED_KEYS = sorted(["tool_root", "input_fn", "output_fn", "env", "cwd"])


def test_init_run_receives_given_keywords(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    tool_root = tmp_path / "toolroot"
    project = tmp_path / "project"
    project.mkdir()
    tool_root.mkdir()
    log_path = tmp_path / "calls.log"
    write_fake_init(tool_root, log_path)
    assert not (project / "gen").exists()

    inputs = []
    outputs = []

    def f(prompt=""):
        inputs.append(prompt)
        return "answer-from-f"

    def g(*args, **kwargs):
        outputs.append(args)

    e = {"HOTDOCS_TEST_MARK": "mark-value", "PATH": os.environ.get("PATH", "")}
    c = str(project)

    rc = hotdocs_cli.run(
        ["init", "dir", "--yes"],
        tool_root=str(tool_root),
        input_fn=f,
        output_fn=g,
        env=e,
        cwd=c,
    )

    records = read_log(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["argv"] == ["dir", "--yes"]
    assert not any(t.startswith("--repo-root") for t in rec["argv"])
    assert rec["keys"] == EXPECTED_KEYS
    desc = rec["desc"]
    assert desc["tool_root"]["real"] == os.path.realpath(str(tool_root))
    assert desc["cwd"]["real"] == os.path.realpath(c)
    assert desc["env"]["items"] == e
    assert desc["env"]["is_os_environ"] is False
    # input_fn and output_fn are exactly f and g
    assert rec.get("input_result") == "answer-from-f"
    assert inputs == ["prompt-from-fake"]
    assert ("message-from-fake",) in outputs
    assert rc == 7


def test_init_run_defaults_filled_in(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    tool_root = tmp_path / "toolroot"
    project = tmp_path / "project"
    project.mkdir()
    tool_root.mkdir()
    log_path = tmp_path / "calls.log"
    write_fake_init(tool_root, log_path)
    monkeypatch.chdir(project)
    monkeypatch.setenv("HOTDOCS_TEST_DEFAULT_MARK", "default-mark")

    rc = hotdocs_cli.run(["init"], tool_root=str(tool_root))

    records = read_log(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["argv"] == []
    assert rec["keys"] == EXPECTED_KEYS
    desc = rec["desc"]
    assert desc["input_fn"]["is_input"] is True
    assert desc["output_fn"]["is_print"] is True
    env_items = desc["env"]["items"]
    assert env_items.get("HOTDOCS_TEST_DEFAULT_MARK") == "default-mark"
    assert env_items == dict(os.environ)
    assert desc["cwd"]["real"] == os.path.realpath(os.getcwd())
    assert desc["cwd"]["real"] == os.path.realpath(str(project))
    assert rc == 7