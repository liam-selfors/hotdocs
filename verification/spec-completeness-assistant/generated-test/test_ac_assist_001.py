# hotdocs-criterion: sha256:c69b15388583c0ec8aac7c37d75ad172162514af03dab0e945663c2a8f09a56b
import spec_completeness_assistant

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component(repo_root, slug, upper):
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " component\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "A fixture component.\n",
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    _write(
        base / "requirements" / (rid + ".md"),
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** — The component MUST return a value.\n",
    )
    _write(
        base / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When it runs\n"
        "Then it returns a value\n"
        "```\n",
    )


LOG_HELPER = (
    "def _log(name):\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(name + '\\n')\n"
    "\n"
)


def _setup(tmp_path, finding_file):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _component(repo_root, "foo", "FOO")
    _component(repo_root, "bar", "BAR")

    header = "LOG = " + repr(str(log_path)) + "\n\n" + LOG_HELPER

    finding = {
        "rule_id": "R-LINT-003",
        "severity": "fail",
        "file": finding_file,
        "line": 12,
        "message": "depends_on references 'comp-baz', which does not exist",
    }

    _write(
        repo_root / "gen" / "spec-linter" / "spec_linter.py",
        header
        + "FINDING = " + repr(finding) + "\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('lint')\n"
        "    return {\n"
        "        'findings': [dict(FINDING)],\n"
        "        'summary': {'hard_failures': 1, 'warnings': 0, 'skipped': 0},\n"
        "    }\n",
    )

    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        header
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('compute_blast_radius')\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n",
    )

    _write(
        repo_root / "gen" / "spec-reviewer" / "spec_reviewer.py",
        header
        + "class _Report:\n"
        "    def __init__(self, targets):\n"
        "        self.targets = list(targets)\n"
        "        self.criteria_checked = []\n"
        "        self.findings = []\n"
        "        self.gaps = []\n"
        "        self.writable = {}\n"
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
        "    _log('check')\n"
        "    return _Report(targets)\n"
        "\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    _log('glossary_judge')\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return (False, 'no conflict')\n"
        "    return judge\n",
    )

    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        header
        + "def complete(prompt, model, backend=None, **params):\n"
        "    _log('complete')\n"
        "    return {\n"
        "        'text': '{\"completeness_score\": 0.5, \"completeness_rationale\": \"ok\"}',\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )

    return repo_root, log_path, finding


def _calls(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line.strip()]


def test_fail_inside_changed_component_halts(tmp_path):
    repo_root, log_path, finding = _setup(
        tmp_path, "specs/components/foo/component.md"
    )

    report = spec_completeness_assistant.assist(
        ["R-FOO-001"], repo_root, model="fake-model"
    )

    lint_findings = list(field(report, "lint_findings"))
    assert len(lint_findings) == 1
    got = lint_findings[0]
    if isinstance(got, dict):
        assert got == finding
    else:
        for key, value in finding.items():
            assert getattr(got, key) == value

    assert field(report, "halted") is True
    assert list(field(report, "predicted_blast_radius")) == []
    assert dict(field(report, "criterion_reviews")) == {}
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []
    assert field(report, "degraded") is False

    calls = _calls(log_path)
    assert calls == ["glossary_judge", "lint"]
    assert "compute_blast_radius" not in calls
    assert "check" not in calls
    assert "complete" not in calls


def test_fail_outside_changed_component_does_not_halt(tmp_path):
    repo_root, log_path, finding = _setup(
        tmp_path, "specs/components/bar/component.md"
    )

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    lint_findings = list(field(report, "lint_findings"))
    assert len(lint_findings) == 1
    got = lint_findings[0]
    if isinstance(got, dict):
        assert got == finding
    else:
        for key, value in finding.items():
            assert getattr(got, key) == value

    assert field(report, "halted") is False

    calls = _calls(log_path)
    assert "lint" in calls
    assert "compute_blast_radius" in calls
    assert calls.index("lint") < calls.index("compute_blast_radius")