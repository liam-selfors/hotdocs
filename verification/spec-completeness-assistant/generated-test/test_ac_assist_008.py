# hotdocs-criterion: sha256:3b482e4177f5fd6e58a5fb278fe7cc53d34da6ce13f7b9f4d4d02857e0fb4521
"""AC-ASSIST-008: assist's to_dict() holds every CompletenessReport field,
and assist creates, modifies or deletes no file under repo_root."""

from pathlib import Path

import spec_completeness_assistant


EXPECTED_FIELDS = [
    "lint_findings",
    "halted",
    "predicted_blast_radius",
    "criterion_reviews",
    "completeness_score",
    "completeness_rationale",
    "redundancy_flags",
    "degraded",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fake_spec_linter(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('lint')\n"
        "    return {\n"
        "        'findings': [],\n"
        "        'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0},\n"
        "    }\n"
    )


def _fake_impact_analyzer(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('compute_blast_radius')\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {\n"
        "                'component_id': " + repr("comp-foo") + ",\n"
        "                'reason': " + repr("direct") + ",\n"
        "                'via': None,\n"
        "                'guarantee_ids': None,\n"
        "            }\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )


def _fake_spec_reviewer(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "class _ReviewReport:\n"
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
        "def check(targets, repo_root, model=None, *, llm_backend=None,\n"
        "          write_proposals=False):\n"
        "    _log('check')\n"
        "    return _ReviewReport(targets)\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    _log('glossary_judge')\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n"
    )


def _fake_llm_endpoint(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def complete(prompt, model, backend=None, **params):\n"
        "    _log('complete')\n"
        "    return {\n"
        "        'text': None,\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': {'category': 'network', 'message': 'unused'},\n"
        "    }\n"
    )


def _build_fixture(repo_root, log_path):
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
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
        "A fixture component.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `x` doubled.\n",
    )
    _write(
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
    _write(
        repo_root / "gen" / "spec-linter" / "spec_linter.py",
        _fake_spec_linter(log_path),
    )
    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        _fake_impact_analyzer(log_path),
    )
    _write(
        repo_root / "gen" / "spec-reviewer" / "spec_reviewer.py",
        _fake_spec_reviewer(log_path),
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        _fake_llm_endpoint(log_path),
    )


def _snapshot(repo_root):
    snap = {}
    for p in sorted(repo_root.rglob("*")):
        rel = p.relative_to(repo_root)
        if "__pycache__" in rel.parts:
            continue
        if p.is_file():
            snap[rel.as_posix()] = p.read_bytes()
    return snap


def test_ac_assist_008_to_dict_hook_and_no_writes_under_repo_root(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # The call log lives outside repo_root so the fakes' own writes never
    # count as a change under repo_root.
    log_path = tmp_path / "calls.log"
    _build_fixture(repo_root, log_path)

    before = _snapshot(repo_root)
    assert before, "fixture should have written files"

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    data = report.to_dict()
    assert isinstance(data, dict)
    for name in EXPECTED_FIELDS:
        assert name in data, "to_dict() is missing field " + repr(name)

    # The three fields a calling tool records accept/override against.
    assert "predicted_blast_radius" in data
    assert "completeness_score" in data
    assert "redundancy_flags" in data
    assert field(data, "predicted_blast_radius") == ["comp-foo"]
    assert field(data, "halted") is False
    assert field(data, "degraded") is True

    after = _snapshot(repo_root)
    assert sorted(after.keys()) == sorted(before.keys()), (
        "files created or deleted under repo_root: "
        + repr(sorted(set(after) ^ set(before)))
    )
    for rel, content in before.items():
        assert after[rel] == content, "file modified under repo_root: " + repr(rel)