# hotdocs-criterion: sha256:d76dd3e1f81b01a0b707bd5846307b8d3453d72df086c357e2b4b7af46823001
import dataclasses
from pathlib import Path

import spec_completeness_assistant


EIGHT_FIELDS = [
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


def _build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: [comp-bar]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    bar_dir = repo_root / "specs" / "components" / "bar"
    _write(
        bar_dir / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/bar/\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Another fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo()` MUST return 1.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
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
    _write(
        bar_dir / "requirements" / "R-BAR-001.md",
        "# R-BAR-001\n"
        "\n"
        "**R-BAR-001** — `bar()` MUST return 2.\n",
    )
    _write(
        bar_dir / "acceptance" / "AC-BAR-001.md",
        "# AC-BAR-001\n"
        "\n"
        "Covers: R-BAR-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When bar() runs\n"
        "Then it returns 2\n"
        "```\n",
    )


def _log_prefix(log_path):
    return (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
    )


def _write_stand_ins(repo_root, log_path):
    gen = repo_root / "gen"
    _write(
        gen / "spec-linter" / "spec_linter.py",
        _log_prefix(log_path)
        + "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('lint')\n"
        "    return {\n"
        "        'findings': [],\n"
        "        'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0},\n"
        "    }\n",
    )
    _write(
        gen / "impact-analyzer" / "impact_analyzer.py",
        _log_prefix(log_path)
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('compute_blast_radius')\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': " + repr("comp-foo") + ", 'reason': 'direct', 'via': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n",
    )
    _write(
        gen / "spec-reviewer" / "spec_reviewer.py",
        _log_prefix(log_path)
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
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {}\n"
        "\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None, write_proposals=False):\n"
        "    _log('check ' + ','.join(targets))\n"
        "    return _Report(targets)\n"
        "\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    _log('glossary_judge')\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n",
    )
    _write(
        gen / "llm-endpoint" / "llm_endpoint.py",
        _log_prefix(log_path)
        + "def complete(prompt, model, backend=None, **params):\n"
        "    _log('complete')\n"
        "    return {\n"
        "        'text': None,\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': {'category': 'network', 'message': 'stand-in'},\n"
        "    }\n",
    )


def test_ac_assist_006_report_returned_normally_and_has_no_gating_members(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fixture(repo_root)
    _write_stand_ins(repo_root, log_path)

    # The fixture component does not list comp-spec-completeness-assistant.
    component_text = (repo_root / "specs" / "components" / "foo" / "component.md").read_text(
        encoding="utf-8"
    )
    assert "comp-spec-completeness-assistant" not in component_text

    report = spec_completeness_assistant.assist(["comp-foo"], repo_root)

    # Returned normally (no exception) as a CompletenessReport.
    assert report is not None
    assert type(report).__name__ == "CompletenessReport"
    assert dataclasses.is_dataclass(report)

    names = [f.name for f in dataclasses.fields(report)]
    assert names == EIGHT_FIELDS

    public = {n for n in dir(report) if not n.startswith("_")}
    assert public == set(EIGHT_FIELDS) | {"to_dict"}

    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    assert set(as_dict.keys()) == set(EIGHT_FIELDS)

    for name in EIGHT_FIELDS:
        field(report, name)