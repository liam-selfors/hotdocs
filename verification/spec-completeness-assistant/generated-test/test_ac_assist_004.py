# hotdocs-criterion: sha256:4f98bbecdc589439b012a25ed618b9e44d625bbc5edbdfd7effd6730573a6fe9
import importlib.util
import json
import sys
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_corpus(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "Doubles numbers.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 `foo(x)` MUST return 2 * x for an integer x.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** \u2014 `foo(x)` MUST raise `TypeError` for a non-integer x.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x is 2\n"
        "When foo(x) runs\n"
        "Then it returns 4\n"
        "```\n",
    )


def write_stand_ins(repo_root, log_path):
    gen = repo_root / "gen"

    linter_src = (
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    return {'findings': [], 'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0}}\n"
    )
    write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    return {'impacted': [{'component_id': 'comp-foo', 'reason': 'direct', 'via': None}],\n"
        "            'precondition_error': None}\n"
    )
    write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        "class _Report:\n"
        "    def __init__(self, targets):\n"
        "        self._d = {\n"
        "            'targets': list(targets),\n"
        "            'criteria_checked': ['AC-FOO-001'],\n"
        "            'findings': [],\n"
        "            'gaps': [],\n"
        "            'writable': {'AC-FOO-001': None},\n"
        "            'lint_findings': [],\n"
        "            'proposals': [],\n"
        "            'degraded': True,\n"
        "        }\n"
        "        for k, v in self._d.items():\n"
        "            setattr(self, k, v)\n"
        "    def __getitem__(self, key):\n"
        "        return self._d[key]\n"
        "    def to_dict(self):\n"
        "        return dict(self._d)\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    return _Report(targets)\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )
    write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    completeness_text = json.dumps(
        {"completeness_score": 0.5, "completeness_rationale": "R-FOO-002 untested"}
    )
    redundancy_text = json.dumps({"redundancy_flags": []})
    endpoint_src = (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "COMPLETENESS = " + repr(completeness_text) + "\n"
        "REDUNDANCY = " + repr(redundancy_text) + "\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    try:\n"
        "        with open(LOG) as f:\n"
        "            n = sum(1 for _ in f)\n"
        "    except FileNotFoundError:\n"
        "        n = 0\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps(prompt) + '\\n')\n"
        "    text = COMPLETENESS if n == 0 else REDUNDANCY\n"
        "    return {'text': text, 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )
    write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def test_ac_assist_004_completeness_prompt_and_reply(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "prompts.log"
    build_corpus(repo_root)
    write_stand_ins(repo_root, log_path)

    report = spec_completeness_assistant.assist(["comp-foo"], repo_root, model="fake-model")

    assert log_path.is_file(), "llm-endpoint stand-in was never called"
    lines = [l for l in log_path.read_text().splitlines() if l.strip()]
    assert lines, "no prompt recorded"
    first_prompt = json.loads(lines[0])

    assert "MUST return 2 * x" in first_prompt
    assert "Then it returns 4" in first_prompt
    assert "No acceptance criterion covers R-FOO-002." in first_prompt

    assert field(report, "completeness_score") == 0.5
    assert field(report, "completeness_rationale") == "R-FOO-002 untested"