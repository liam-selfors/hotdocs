# hotdocs-criterion: sha256:4509be9e920cc8edec17b0e925730bca77e52f223152ec63da2ac9f565f8b224
import dataclasses
from pathlib import Path

import spec_completeness_assistant


FIELDS = [
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(
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
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo` MUST return its input unchanged.\n",
    )
    write(
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


def build_stand_ins(repo_root, log_path):
    gen = repo_root / "gen"
    log_line = (
        "def _log(line):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
    )

    write(
        gen / "spec-linter" / "spec_linter.py",
        log_line
        + "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('lint')\n"
        "    return {\n"
        "        'findings': [],\n"
        "        'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0},\n"
        "    }\n",
    )

    write(
        gen / "impact-analyzer" / "impact_analyzer.py",
        log_line
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('compute_blast_radius ' + ','.join(changed_ids))\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None,\n"
        "             'guarantee_ids': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n",
    )

    write(
        gen / "spec-reviewer" / "spec_reviewer.py",
        log_line
        + "class _Report:\n"
        "    def to_dict(self):\n"
        "        return {}\n"
        "\n"
        "\n"
        "def check(targets, repo_root, model=None, *, llm_backend=None,\n"
        "          write_proposals=False):\n"
        "    _log('check ' + ','.join(targets))\n"
        "    return _Report()\n"
        "\n"
        "\n"
        "def glossary_judge(model, llm_backend=None):\n"
        "    _log('glossary_judge')\n"
        "    def judge(term, local_text, glossary_text):\n"
        "        return None\n"
        "    return judge\n",
    )

    write(
        gen / "llm-endpoint" / "llm_endpoint.py",
        log_line
        + "def complete(prompt, model, backend=None, **params):\n"
        "    _log('complete')\n"
        "    return {\n"
        "        'text': None,\n"
        "        'model': model,\n"
        "        'backend': 'mock',\n"
        "        'model_call_error': {'category': 'network', 'message': 'stand-in'},\n"
        "    }\n",
    )


def test_ac_assist_006_report_returned_and_has_no_gating_members(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_fixture(repo_root)
    build_stand_ins(repo_root, log_path)

    component_md = (repo_root / "specs" / "components" / "foo" / "component.md").read_text(
        encoding="utf-8"
    )
    assert "comp-spec-completeness-assistant" not in component_md

    # Returns normally rather than raising.
    report = spec_completeness_assistant.assist(["comp-foo"], repo_root)

    assert report is not None
    assert type(report).__name__ == "CompletenessReport"

    # The stand-ins were the ones exercised.
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert "lint" in calls
    assert "compute_blast_radius comp-foo" in calls
    assert "check comp-foo" in calls
    assert "complete" not in calls
    assert "glossary_judge" not in calls

    # Exactly eight dataclass fields, in order.
    assert dataclasses.is_dataclass(report)
    assert [f.name for f in dataclasses.fields(report)] == FIELDS

    # Public members are exactly the eight fields and to_dict().
    public = {name for name in dir(report) if not name.startswith("_")}
    assert public == set(FIELDS) | {"to_dict"}

    # Every field is readable and descriptive; to_dict holds every field.
    for name in FIELDS:
        field(report, name)
    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    assert set(as_dict.keys()) == set(FIELDS)
    assert field(report, "halted") is False
    assert field(report, "degraded") is True