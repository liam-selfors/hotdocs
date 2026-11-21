# hotdocs-criterion: sha256:584222b98870802da0afde1c96191428bbe047366276156f48c0443511eccfac
import json
import os
import shlex
import sys
from pathlib import Path

import pytest

import agentic_generator


MODEL = "anthropic:claude-sonnet-5"

WIDGET_SRC = "import os\nKEY = os.environ.get('ANTHROPIC_API_KEY')\n"

SCRATCH_TEST_SRC = (
    "import socket\n"
    "import pytest\n"
    "import widget\n"
    "\n"
    "\n"
    "def test_w():\n"
    "    assert widget.KEY is None\n"
    "    with pytest.raises(OSError):\n"
    "        socket.create_connection(('1.1.1.1', 80), timeout=3)\n"
)

FULL_SCRIPT = [
    ["write_file", {"path": "work/widget.py", "content": WIDGET_SRC}],
    ["write_file", {"path": "scratch/test_w.py", "content": SCRATCH_TEST_SRC}],
    ["check_import", {}],
    ["run_scratch_tests", {}],
    ["finish", {"summary": "done"}],
]

FINISH_ONLY_SCRIPT = [
    ["finish", {"summary": "done"}],
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_sandbox_exec():
    return sys.platform == "darwin" and os.path.exists("/usr/bin/sandbox-exec")


GENERATOR_SRC_HEAD = (
    "import dataclasses\n"
    "import json\n"
    "from dataclasses import dataclass, field\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class GenerationResult:\n"
    "    component_id: str = ''\n"
    "    spec_bundle_hash: str = ''\n"
    "    model: str = ''\n"
    "    prompt_version: str = ''\n"
    "    cache_hit: bool = False\n"
    "    files: dict = field(default_factory=dict)\n"
    "    model_call_error: object = None\n"
    "    refused: object = None\n"
    "    retry_feedback: object = None\n"
    "    mode: str = 'single'\n"
    "    transcript_sha256: object = None\n"
    "    turns: int = 1\n"
    "    tool_calls: int = 0\n"
    "    isolation: object = None\n"
    "\n"
)


def generator_src(log_dir):
    return (
        GENERATOR_SRC_HEAD
        + "LOG_DIR = " + repr(str(log_dir)) + "\n"
        + "\n"
        + "def _record(name, payload):\n"
        + "    with open(Path(LOG_DIR) / name, 'a', encoding='utf-8') as fh:\n"
        + "        fh.write(json.dumps(payload, default=str) + '\\n')\n"
        + "\n"
        + "def check_write_allowed(bundle, repo_root=None):\n"
        + "    return None\n"
        + "\n"
        + "def render_prompt_sections(bundle, retry_feedback=None):\n"
        + "    return [('Spec', 'SPEC TEXT'), ('Component interface', 'IFACE TEXT')]\n"
        + "\n"
        + "def write_files(component_id, files, repo_root=None):\n"
        + "    _record('write_files.log', [component_id, files, str(repo_root)])\n"
        + "\n"
        + "def check_assets(component_id, files, repo_root=None):\n"
        + "    _record('check_assets.log', [component_id, files, str(repo_root)])\n"
        + "    for content in files.values():\n"
        + "        if 'bad' in content:\n"
        + "            return ('malformed_layout', ['static/app.txt: bad'])\n"
        + "    return (None, [])\n"
        + "\n"
        + "def check_asset_environment(component_id, repo_root=None):\n"
        + "    if repo_root is not None and (Path(repo_root) / 'NO_ENV').exists():\n"
        + "        return ('environment', ['fake needs fakeprog >= 2'])\n"
        + "    return (None, [])\n"
    )


def loop_src(script_path, results_path, args_path):
    return (
        "import json\n"
        "\n"
        "SCRIPT = " + repr(str(script_path)) + "\n"
        "RESULTS = " + repr(str(results_path)) + "\n"
        "ARGS = " + repr(str(args_path)) + "\n"
        "\n"
        "\n"
        "class _ToolLoopResult:\n"
        "    def __init__(self, text, transcript, turns, tool_calls, stop, model_call_error):\n"
        "        self.text = text\n"
        "        self.transcript = transcript\n"
        "        self.turns = turns\n"
        "        self.tool_calls = tool_calls\n"
        "        self.stop = stop\n"
        "        self.model_call_error = model_call_error\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'text': self.text, 'transcript': self.transcript, 'turns': self.turns,\n"
        "                'tool_calls': self.tool_calls, 'stop': self.stop,\n"
        "                'model_call_error': self.model_call_error}\n"
        "\n"
        "\n"
        "def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,\n"
        "                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,\n"
        "                  claude_command='claude'):\n"
        "    with open(ARGS, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'system': system, 'prompt': prompt, 'model': model,\n"
        "                             'tools': tools, 'max_turns': max_turns,\n"
        "                             'max_tool_calls': max_tool_calls,\n"
        "                             'wall_seconds': wall_seconds,\n"
        "                             'repo_root': str(repo_root),\n"
        "                             'claude_command': claude_command}, default=str) + '\\n')\n"
        "    with open(SCRIPT, encoding='utf-8') as fh:\n"
        "        steps = json.load(fh)\n"
        "    calls = 0\n"
        "    for name, arguments in steps:\n"
        "        text, is_error = execute(name, arguments)\n"
        "        calls += 1\n"
        "        with open(RESULTS, 'a', encoding='utf-8') as fh:\n"
        "            fh.write(json.dumps([name, arguments, text, is_error]) + '\\n')\n"
        "    return _ToolLoopResult('done', [{'role': 'user', 'content': prompt}], 1, calls,\n"
        "                           'end_turn', None)\n"
    )


def kind_python_src(interpreter):
    return (
        "from pathlib import Path\n"
        "\n"
        "KIND = 'python'\n"
        "INTERPRETER = " + repr(str(interpreter)) + "\n"
        "\n"
        "\n"
        "class AssetError(Exception):\n"
        "    pass\n"
        "\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {'names': []}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {'ok': True, 'reason': None, 'versions': {}, 'lockfile_sha256': None,\n"
        "            'interpreter': INTERPRETER}\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': 'GEN GUIDANCE', 'test_author': 'TEST GUIDANCE'}\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        raise AssetError('not supported')\n"
        "    return run\n"
        "\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )


class Harness:
    def __init__(self, base, script):
        self.base = Path(base)
        self.repo_root = self.base / "repo"
        self.logs = self.base / "logs"
        self.logs.mkdir(parents=True, exist_ok=True)
        self.script_path = self.logs / "script.json"
        self.results_path = self.logs / "results.jsonl"
        self.args_path = self.logs / "loop_args.jsonl"
        self.script_path.write_text(json.dumps(script), encoding="utf-8")

        gen_dir = self.repo_root / "gen" / "generator"
        gen_dir.mkdir(parents=True)
        (gen_dir / "generator.py").write_text(generator_src(self.logs), encoding="utf-8")

        loop_dir = self.repo_root / "gen" / "llm-tool-endpoint"
        loop_dir.mkdir(parents=True)
        (loop_dir / "llm_tool_endpoint.py").write_text(
            loop_src(self.script_path, self.results_path, self.args_path), encoding="utf-8"
        )

    def reset(self):
        if self.results_path.exists():
            self.results_path.unlink()

    def results(self):
        if not self.results_path.exists():
            return []
        out = []
        for line in self.results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def result_for(self, name):
        matches = [r for r in self.results() if r[0] == name]
        assert matches, "no recorded result for " + name + ": " + repr(self.results())
        return matches[0]

    def run(self, **kwargs):
        self.reset()
        bundle = {
            "component_id": "comp-widget",
            "spec_bundle_hash": "sha256:" + "0" * 64,
            "hint_code": None,
        }
        return agentic_generator.generate_agentic(
            bundle, MODEL, repo_root=self.repo_root, **kwargs
        )


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")


@pytest.fixture
def no_sandbox(monkeypatch):
    monkeypatch.setattr(agentic_generator, "SANDBOX_EXEC", "/nonexistent/sandbox")
    monkeypatch.setattr(agentic_generator, "BWRAP", "/nonexistent/sandbox")


def test_sandbox_exec_runs_both_tools(tmp_path, api_key):
    if not has_sandbox_exec():
        pytest.skip("platform without /usr/bin/sandbox-exec")
    h = Harness(tmp_path, FULL_SCRIPT)
    result = h.run()

    check = h.result_for("check_import")
    assert check[2].startswith("0\n"), repr(check)
    tests = h.result_for("run_scratch_tests")
    assert tests[2].startswith("0\n"), repr(tests)
    assert field(result, "isolation") == "sandbox-exec"


def test_sandbox_exec_isolation_when_nothing_ran(tmp_path, api_key):
    if not has_sandbox_exec():
        pytest.skip("platform without /usr/bin/sandbox-exec")
    h = Harness(tmp_path, FINISH_ONLY_SCRIPT)
    result = h.run()

    names = [r[0] for r in h.results()]
    assert "check_import" not in names
    assert "run_scratch_tests" not in names
    assert field(result, "isolation") == "sandbox-exec"


def test_no_sandbox_refuses_then_unisolated_runs(tmp_path, api_key, no_sandbox):
    h = Harness(tmp_path, FULL_SCRIPT)

    result = h.run()
    check = h.result_for("check_import")
    assert check[2] == "no OS sandbox available: code is not run", repr(check)
    assert check[3] is True
    assert field(result, "isolation") == "none"

    result = h.run(allow_unisolated_exec=True)
    check = h.result_for("check_import")
    assert check[2].startswith("0\n"), repr(check)
    assert field(result, "isolation") == "unisolated"


def test_provisioned_interpreter_used_once_per_run(tmp_path, api_key, no_sandbox):
    h = Harness(tmp_path, FULL_SCRIPT)

    interp_dir = tmp_path / "interp"
    interp_dir.mkdir()
    interp_log = interp_dir / "interp.log"
    interpreter = interp_dir / "python.sh"
    interpreter.write_text(
        "#!/bin/sh\n"
        + "echo call >> " + shlex.quote(str(interp_log)) + "\n"
        + "exec " + shlex.quote(sys.executable) + " \"$@\"\n",
        encoding="utf-8",
    )
    os.chmod(interpreter, 0o755)
    assert h.repo_root.resolve() not in interpreter.resolve().parents

    kind_dir = h.repo_root / "gen" / "kind-python"
    kind_dir.mkdir(parents=True)
    (kind_dir / "kind_python.py").write_text(kind_python_src(interpreter), encoding="utf-8")

    h.run(allow_unisolated_exec=True)

    check = h.result_for("check_import")
    assert check[2].startswith("0\n"), repr(check)

    assert interp_log.exists(), "interpreter script was never run"
    lines = [l for l in interp_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2, repr(lines)