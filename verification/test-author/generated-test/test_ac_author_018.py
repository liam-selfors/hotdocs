# hotdocs-criterion: sha256:02be13d2fcc16bfafb2e6dde499822ca29199d5b49cb6809b5f47b650d16ca5e
import json
import re
from pathlib import Path

import test_author


EXPECTED_LINE = (
    "- A unit file (`constraints.md`, or anything under `requirements/`, "
    "`interface/` or `acceptance/`) carries no frontmatter at all."
)

REPLY_BODY = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, calls_log):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(calls_log)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock_backend(prompts_log):
    def backend(prompt, model, **params):
        with open(prompts_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(prompt) + "\n")
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + REPLY_BODY
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_ac_author_018_prompt_holds_unit_file_frontmatter_line(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    prompts_log = logs / "prompts.jsonl"
    probe_log = logs / "probe_calls.log"

    write_probe_stand_in(repo_root, probe_log)
    monkeypatch.chdir(repo_root)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - The maker MUST make widgets.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_mock_backend(prompts_log)
    )

    assert field(result, "model_call_error") is None

    assert prompts_log.is_file(), "the mock model was never called"
    lines = [ln for ln in prompts_log.read_text(encoding="utf-8").splitlines() if ln]
    assert lines, "no prompt was recorded"
    first_prompt = json.loads(lines[0])

    assert EXPECTED_LINE in first_prompt.splitlines()