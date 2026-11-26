# hotdocs-criterion: sha256:db25f57ae94943b83627f37b54706c9f1e8683c5b4df7a53a2c41c14e316dea6
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_dict(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does one small thing for its users.\n"
    "\n"
    "## Rationale\n"
    "\n"
    "Chosen in D1.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: doing the one small thing.\n"
    "- Out of scope: everything else.\n"
    "\n"
    "## Definitions\n"
    "\n"
    "- **Foo** \u2014 a widget the team sells by weight.\n"
    "\n"
    "## Behavior\n"
    "\n"
    "See `requirements/`.\n"
    "\n"
    "## Interfaces\n"
    "\n"
    "See `interface/`.\n"
    "\n"
    "## Data\n"
    "\n"
    "See `interface/data/`.\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "See `acceptance/`.\n"
    "\n"
    "## Non-functional constraints\n"
    "\n"
    "See `constraints.md`.\n"
    "\n"
    "## Open questions\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial draft.\n"
)


def write_corpus(repo_root: Path) -> None:
    files = {
        "specs/glossary.md": "# Glossary\n\n- **Foo** \u2014 a made thing.\n",
        "specs/decisions/D1.md": (
            "---\n"
            "id: D1\n"
            "title: Foo exists\n"
            "status: draft\n"
            "owners: [pipeline-team]\n"
            "---\n"
            "\n"
            "# D1: Foo exists\n"
            "\n"
            "We decided foo should exist.\n"
        ),
        "specs/components/foo/component.md": COMPONENT_MD,
        "specs/components/foo/requirements/R-FOO-001.md": (
            "**R-FOO-001** \u2014 Foo MUST do the one small thing (D1).\n"
        ),
        "specs/components/foo/acceptance/AC-FOO-001.md": (
            "# AC-FOO-001\n"
            "\n"
            "Covers: R-FOO-001\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given a foo\n"
            "When it runs\n"
            "Then it does the one small thing\n"
            "```\n"
        ),
        "specs/components/foo/constraints.md": (
            "# Constraints\n\n- None beyond the defaults.\n"
        ),
        # the one-warn edit: an interface/cli.md
        "specs/components/foo/interface/cli.md": (
            "# CLI\n\n```\nfoo run\n```\n"
        ),
    }
    for rel, text in files.items():
        p = repo_root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


COMPONENT_REL = "specs/components/foo/component.md"


def lint015(report):
    return [
        f
        for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-015"
        and str(field(f, "file")).replace("\\", "/") == COMPONENT_REL
    ]


def count(report, severity):
    return sum(1 for f in field(report, "findings") if field(f, "severity") == severity)


def check_counts(report):
    n_fail = count(report, "fail")
    n_warn = count(report, "warn")
    n_skip = count(report, "skipped")
    assert field(report, "hard_failures") == n_fail
    assert field(report, "warnings") == n_warn
    assert field(report, "skipped") == n_skip
    summary = field(as_dict(report.to_json()), "summary")
    assert summary["hard_failures"] == n_fail
    assert summary["warnings"] == n_warn
    assert summary["skipped"] == n_skip


def test_no_judge_skipped_and_counts(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    found = lint015(report)
    assert len(found) == 1
    assert field(found[0], "severity") == "skipped"
    check_counts(report)


def test_strict_counts_warns_as_failures(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path, strict=True)
    n_fail = count(report, "fail")
    n_warn = count(report, "warn")
    assert n_warn >= 1
    assert field(report, "hard_failures") == n_fail + n_warn


def test_judge_conflict_fail_with_rationale(tmp_path):
    write_corpus(tmp_path)
    calls = []

    def judge(term, local_text, glossary_text):
        calls.append((term, local_text, glossary_text))
        return (True, "contradicts the glossary")

    report = spec_linter.lint(None, tmp_path, judge=judge)
    assert calls
    found = lint015(report)
    assert len(found) == 1
    assert field(found[0], "severity") == "fail"
    js = as_dict(found[0].to_json())
    assert js["rationale"] == "contradicts the glossary"
    check_counts(report)


def test_judge_consistent_absent(tmp_path):
    write_corpus(tmp_path)

    def judge(term, local_text, glossary_text):
        return (False, "consistent")

    report = spec_linter.lint(None, tmp_path, judge=judge)
    assert lint015(report) == []
    check_counts(report)


def test_judge_none_skipped_no_rationale(tmp_path):
    write_corpus(tmp_path)

    def judge(term, local_text, glossary_text):
        return None

    report = spec_linter.lint(None, tmp_path, judge=judge)
    found = lint015(report)
    assert len(found) == 1
    assert field(found[0], "severity") == "skipped"
    js = as_dict(found[0].to_json())
    assert "rationale" not in js
    check_counts(report)