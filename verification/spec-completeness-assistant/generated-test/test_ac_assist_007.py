# hotdocs-criterion: sha256:95a05f418b546be04e4638c29512b6d81678dd9b5606f104878dbfcaf11cfa25
import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


WARN_FINDING = {
    "rule_id": "R-LINT-010",
    "severity": "warn",
    "file": "specs/components/foo/requirements/R-FOO-001.md",
    "line": 3,
    "message": "a stand-in warning",
}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(
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
        "A fixture component.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 `foo` MUST return its input unchanged.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an input x\n"
        "When foo(x) runs\n"
        "Then it returns x\n"
        "```\n",
    )


LOG_HELPER = (
    "import json\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
)


def _write_stand_ins(repo_root, log_path):
    header = "LOG_PATH = " + repr(str(log_path)) + "\n" + LOG_HELPER
    gen = repo_root / "gen"

    _write(
        gen / "spec-linter" / "spec_linter.py",
        header
        + "WARN_FINDING = " + repr(WARN_FINDING) + "\n"
        + "\n"
        + "def lint(paths, repo_root, strict=False, judge=None):\n"
        + "    _log({'call': 'lint', 'paths': None if paths is None else [str(p) for p in paths],\n"
        + "          'repo_root': str(repo_root), 'strict': strict,\n"
        + "          'judge_is_none': judge is None, 'judge_repr': repr(judge)})\n"
        + "    return {'findings': [dict(WARN_FINDING)],\n"
        + "            'summary': {'hard_failures': 0, 'warnings': 1, 'skipped': 0}}\n",
    )

    _write(
        gen / "impact-analyzer" / "impact_analyzer.py",
        header
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        + "    _log({'call': 'compute_blast_radius', 'changed_ids': list(changed_ids),\n"
        + "          'repo_root': str(repo_root)})\n"
        + "    return {'impacted': [{'component_id': 'comp-foo', 'reason': 'direct', 'via': None}],\n"
        + "            'precondition_error': None}\n",
    )

    _write(
        gen / "spec-reviewer" / "spec_reviewer.py",
        header
        + "class _Report:\n"
        + "    def to_dict(self):\n"
        + "        return {'findings': []}\n"
        + "\n"
        + "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        + "    _log({'call': 'check', 'targets': list(targets), 'repo_root': str(repo_root),\n"
        + "          'model': model, 'llm_backend_is_none': llm_backend is None,\n"
        + "          'write_proposals': write_proposals})\n"
        + "    return _Report()\n"
        + "\n"
        + "def glossary_judge(model, llm_backend=None):\n"
        + "    _log({'call': 'glossary_judge', 'model': model})\n"
        + "    def judge(term, local_text, glossary_text):\n"
        + "        return None\n"
        + "    return judge\n",
    )

    _write(
        gen / "llm-endpoint" / "llm_endpoint.py",
        header
        + "def complete(prompt, model, backend=None, **params):\n"
        + "    _log({'call': 'complete', 'model': model})\n"
        + "    return {'text': '{}', 'model': model, 'backend': 'mock', 'model_call_error': None}\n",
    )


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ac_assist_007_no_model_degraded_run(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "calls.log"

    _build_corpus(repo_root)
    _write_stand_ins(repo_root, log_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    findings = list(field(report, "lint_findings"))
    assert len(findings) == 1
    assert findings[0] == WARN_FINDING
    assert field(findings[0], "severity") == "warn"

    assert list(field(report, "predicted_blast_radius")) == ["comp-foo"]

    reviews = field(report, "criterion_reviews")
    assert "comp-foo" in reviews

    assert field(report, "degraded") is True
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []

    entries = _read_log(log_path)
    calls = [e["call"] for e in entries]

    lint_calls = [e for e in entries if e["call"] == "lint"]
    assert lint_calls, "lint stand-in was never called: " + repr(calls)
    for entry in lint_calls:
        assert entry["judge_is_none"] is True, entry

    assert "compute_blast_radius" in calls
    check_calls = [e for e in entries if e["call"] == "check"]
    assert any(e["targets"] == ["comp-foo"] for e in check_calls), check_calls

    assert "complete" not in calls, calls
    assert "glossary_judge" not in calls, calls