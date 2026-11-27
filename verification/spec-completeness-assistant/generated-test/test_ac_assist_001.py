# hotdocs-criterion: sha256:d9fbdaf6def49e97772c51063afe020fc571f2f54addbf18e185022cc043ec60
import sys
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    for slug, upper in (("foo", "FOO"), ("bar", "BAR")):
        comp_dir = repo_root / "specs" / "components" / slug
        _write(
            comp_dir / "component.md",
            "---\n"
            + "id: comp-" + slug + "\n"
            + "title: " + slug.capitalize() + " component\n"
            + "status: draft\n"
            + "owners: [test-team]\n"
            + "depends_on: []\n"
            + "sealed: true\n"
            + "source_path: legacy/" + slug + "/\n"
            + "---\n"
            + "\n"
            + "# " + slug.capitalize() + "\n"
            + "\n"
            + "## Purpose\n"
            + "\n"
            + "A fixture component.\n",
        )
        req_id = "R-" + upper + "-001"
        ac_id = "AC-" + upper + "-001"
        _write(
            comp_dir / "requirements" / (req_id + ".md"),
            "# " + req_id + "\n"
            + "\n"
            + "**" + req_id + "** — MUST do the " + slug + " thing.\n",
        )
        _write(
            comp_dir / "acceptance" / (ac_id + ".md"),
            "# " + ac_id + "\n"
            + "\n"
            + "Covers: " + req_id + "\n"
            + "Kind: generated-test\n"
            + "\n"
            + "```gherkin\n"
            + "Given a " + slug + "\n"
            + "When it runs\n"
            + "Then the " + slug + " thing happens\n"
            + "```\n",
        )


def _write_fakes(repo_root, log_path, finding):
    log = repr(str(log_path))

    def log_line(name):
        return (
            "    with open(" + log + ", 'a', encoding='utf-8') as _fh:\n"
            + "        _fh.write(" + repr(name) + " + '\\n')\n"
        )

    linter_src = (
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        + log_line("lint")
        + "    finding = " + repr(finding) + "\n"
        + "    hard = 1 if finding['severity'] == 'fail' else 0\n"
        + "    return {'findings': [finding], 'summary': "
        + "{'hard_failures': hard, 'warnings': 0, 'skipped': 0}}\n"
    )
    _write(repo_root / "gen" / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        "def compute_blast_radius(changed_ids, repo_root):\n"
        + log_line("compute_blast_radius")
        + "    return {'impacted': [{'component_id': 'comp-foo', 'reason': 'direct', "
        + "'via': None, 'guarantee_ids': None}], 'precondition_error': None}\n"
    )
    _write(repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py", impact_src)

    reviewer_src = (
        "class ReviewReport:\n"
        + "    def __init__(self, targets):\n"
        + "        self._data = {'targets': list(targets), 'criteria_checked': [], "
        + "'findings': [], 'gaps': [], 'writable': {}, 'lint_findings': [], "
        + "'proposals': [], 'degraded': True}\n"
        + "        for _k, _v in self._data.items():\n"
        + "            setattr(self, _k, _v)\n"
        + "    def __getitem__(self, key):\n"
        + "        return self._data[key]\n"
        + "    def to_dict(self):\n"
        + "        return dict(self._data)\n"
        + "\n"
        + "def _judge(term, local_text, glossary_text):\n"
        + "    return None\n"
        + "\n"
        + "def glossary_judge(model, llm_backend=None):\n"
        + log_line("glossary_judge")
        + "    return _judge\n"
        + "\n"
        + "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        + log_line("check")
        + "    return ReviewReport(targets)\n"
    )
    _write(repo_root / "gen" / "spec-reviewer" / "spec_reviewer.py", reviewer_src)

    endpoint_src = (
        "def complete(prompt, model, backend=None, **params):\n"
        + log_line("complete")
        + "    return {'text': '{\"completeness_score\": 1.0, \"completeness_rationale\": \"ok\"}', "
        + "'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def _make_finding(file):
    return {
        "rule_id": "R-LINT-003",
        "severity": "fail",
        "file": file,
        "line": 12,
        "message": "depends_on references 'comp-baz', which does not exist",
    }


def test_fail_inside_changed_component_halts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    log_path = tmp_path / "calls.log"
    finding = _make_finding("specs/components/foo/component.md")
    _write_fakes(repo_root, log_path, finding)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root, model="fake-model")

    assert list(field(report, "lint_findings")) == [finding]
    assert field(report, "halted") is True
    assert list(field(report, "predicted_blast_radius")) == []
    assert dict(field(report, "criterion_reviews")) == {}
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []
    assert field(report, "degraded") is False

    calls = _read_log(log_path)
    assert calls == ["glossary_judge", "lint"]
    assert "compute_blast_radius" not in calls
    assert "check" not in calls
    assert "complete" not in calls


def test_fail_outside_changed_component_does_not_halt(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    log_path = tmp_path / "calls.log"
    finding = _make_finding("specs/components/bar/component.md")
    _write_fakes(repo_root, log_path, finding)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    assert list(field(report, "lint_findings")) == [finding]
    assert field(report, "halted") is False

    calls = _read_log(log_path)
    assert "lint" in calls
    assert "compute_blast_radius" in calls
    assert calls.index("lint") < calls.index("compute_blast_radius")