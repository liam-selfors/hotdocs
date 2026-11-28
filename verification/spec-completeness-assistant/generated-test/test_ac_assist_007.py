# hotdocs-criterion: sha256:e59ff001285edf17e15ea0f8972d93f0d922934cdca484318733c314dfff09a2
import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


WARN_FINDING = {
    "rule_id": "R-LINT-009",
    "severity": "warn",
    "file": "specs/components/foo/component.md",
    "line": 3,
    "message": "a warning about foo",
}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _log_prelude(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(rec):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(rec) + '\\n')\n"
        "\n"
    )


def _build_corpus(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [foo-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does foo things.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo()` MUST return 1.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When foo() runs\n"
        "Then it returns 1\n"
        "```\n",
    )


def _write_fakes(repo_root, log_path):
    gen = repo_root / "gen"

    linter_src = (
        _log_prelude(log_path)
        + "FINDING = " + repr(WARN_FINDING) + "\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log({'fn': 'lint', 'paths_is_none': paths is None,\n"
        "          'strict': bool(strict), 'judge_is_none': judge is None})\n"
        "    return {'findings': [dict(FINDING)],\n"
        "            'summary': {'hard_failures': 0, 'warnings': 1, 'skipped': 0}}\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        _log_prelude(log_path)
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log({'fn': 'compute_blast_radius', 'changed_ids': list(changed_ids)})\n"
        "    return {'impacted': [{'component_id': 'comp-foo', 'reason': 'direct',\n"
        "                          'via': None, 'guarantee_ids': None}],\n"
        "            'precondition_error': None}\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        _log_prelude(log_path)
        + "class _Report:\n"
        "    def to_dict(self):\n"
        "        return {'findings': []}\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    _log({'fn': 'check', 'targets': list(targets), 'model_is_none': model is None})\n"
        "    return _Report()\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    _log({'fn': 'glossary_judge'})\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        _log({'fn': 'judge_call'})\n"
        "        return None\n"
        "    return judge\n"
    )
    _write(gen / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    endpoint_src = (
        _log_prelude(log_path)
        + "def complete(prompt, model, backend=None, **params):\n"
        "    _log({'fn': 'complete'})\n"
        "    return {'text': '{}', 'model': model, 'backend': 'mock',\n"
        "            'model_call_error': None}\n"
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


def test_ac_assist_007_degraded_mode_makes_no_model_call(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    _build_corpus(repo_root)
    _write_fakes(repo_root, log_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    # R-ASSIST-001: lint findings passed through unchanged
    lint_findings = list(field(report, "lint_findings"))
    assert lint_findings == [WARN_FINDING]

    # R-ASSIST-002: predicted blast radius
    assert list(field(report, "predicted_blast_radius")) == ["comp-foo"]

    # R-ASSIST-003: criterion reviews
    reviews = field(report, "criterion_reviews")
    assert "comp-foo" in reviews

    # R-ASSIST-004/005 reported as skipped
    assert field(report, "degraded") is True
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []

    calls = _read_log(log_path)
    fns = [c["fn"] for c in calls]

    lint_calls = [c for c in calls if c["fn"] == "lint"]
    assert len(lint_calls) >= 1
    assert all(c["judge_is_none"] for c in lint_calls)

    assert "complete" not in fns
    assert "glossary_judge" not in fns
    assert "judge_call" not in fns