# hotdocs-criterion: sha256:80d8cb154b1576bc7e042c14445fe97daf761c4794b3d8915dd8630aaf95e2a2
import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


R_FOO_001_TEXT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `foo(x)` MUST return 2 * x.\n"
)

R_FOO_002_TEXT = (
    "# R-FOO-002\n"
    "\n"
    "**R-FOO-002** \u2014 `foo(x)` MUST raise `TypeError` when `x` is not a number.\n"
)

AC_FOO_001_TEXT = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x is 2\n"
    "When foo(x) runs\n"
    "Then it returns 4\n"
    "```\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "Doubles numbers.\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", R_FOO_001_TEXT)
    _write(comp / "requirements" / "R-FOO-002.md", R_FOO_002_TEXT)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_FOO_001_TEXT)
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def _write_fakes(repo_root, log_path):
    gen = repo_root / "gen"

    linter_src = (
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    return {'findings': [], 'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0}}\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None, 'guarantee_ids': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        "class _Report:\n"
        "    def __init__(self, targets):\n"
        "        self.targets = list(targets)\n"
        "        self.criteria_checked = ['AC-FOO-001']\n"
        "        self.findings = []\n"
        "        self.gaps = []\n"
        "        self.writable = {'AC-FOO-001': None}\n"
        "        self.lint_findings = []\n"
        "        self.proposals = []\n"
        "        self.degraded = True\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'targets': list(self.targets),\n"
        "            'criteria_checked': list(self.criteria_checked),\n"
        "            'findings': list(self.findings),\n"
        "            'gaps': list(self.gaps),\n"
        "            'writable': dict(self.writable),\n"
        "            'lint_findings': list(self.lint_findings),\n"
        "            'proposals': list(self.proposals),\n"
        "            'degraded': self.degraded,\n"
        "        }\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return self.to_dict()[key]\n"
        "\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    return _Report(targets)\n"
        "\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )
    _write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    completeness_reply = json.dumps(
        {"completeness_score": 0.5, "completeness_rationale": "R-FOO-002 untested"}
    )
    redundancy_reply = json.dumps({"redundancy_flags": []})
    endpoint_src = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "COMPLETENESS_REPLY = " + repr(completeness_reply) + "\n"
        "REDUNDANCY_REPLY = " + repr(redundancy_reply) + "\n"
        "\n"
        "\n"
        "def _count():\n"
        "    try:\n"
        "        with open(LOG_PATH, 'r', encoding='utf-8') as fh:\n"
        "            return sum(1 for line in fh if line.strip())\n"
        "    except FileNotFoundError:\n"
        "        return 0\n"
        "\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    index = _count()\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'prompt': prompt, 'model': model}) + '\\n')\n"
        "    text = COMPLETENESS_REPLY if index == 0 else REDUNDANCY_REPLY\n"
        "    return {'text': text, 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ac_assist_004_completeness_prompt_and_reply(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "llm_calls.log"

    _build_fixture(repo_root)
    _write_fakes(repo_root, log_path)

    report = spec_completeness_assistant.assist(
        ["comp-foo"], repo_root, model="fake-model"
    )

    calls = _read_log(log_path)
    assert len(calls) >= 1, "llm-endpoint stand-in was never called"

    first_prompt = calls[0]["prompt"]
    assert "MUST return 2 * x" in first_prompt
    assert "Then it returns 4" in first_prompt
    assert "No acceptance criterion covers R-FOO-002." in first_prompt

    assert field(report, "completeness_score") == 0.5
    assert field(report, "completeness_rationale") == "R-FOO-002 untested"