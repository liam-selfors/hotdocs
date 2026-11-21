# hotdocs-criterion: sha256:0633d928ad47f8ecff01c0f4cf9f2f1901159f60831ac596342a94a11657ca4c
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PURPOSE_SENTENCE = (
    "This fixture component accepts plain input records, normalizes their "
    "fields, and hands the cleaned records to whichever caller asked for them. "
)


def _build_corpus(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **Widget** — a reusable rectangular panel shown on the operations "
        "dashboard, holding one chart and its legend.\n",
    )

    # Purpose well above 80 words (warn) but below 150 (no fail).
    purpose = (PURPOSE_SENTENCE * 5).strip()

    comp_dir = specs / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose
        + "\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: normalizing records.\n"
        "- Out of scope: storing records.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "- **Widget** — inside this component, a purple spinning token that "
        "rotates forever and never displays any chart at all.\n"
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
        "- Initial draft.\n",
    )

    # A requirement file above 250 words (warn) but below 500 (no fail).
    filler = " ".join(["normalized"] * 270)
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The component MUST trim surrounding whitespace from "
        "every field of every record it returns.\n"
        "\n"
        + filler
        + "\n",
    )

    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a record with field \"name\" set to \"  a  \"\n"
        "When the record is normalized\n"
        "Then field \"name\" is \"a\"\n"
        "```\n",
    )

    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Normalizing one record takes under 1 ms, measured by a benchmark.\n",
    )


def _report_json(report):
    data = report.to_json()
    if isinstance(data, (str, bytes)):
        data = json.loads(data)
    return data


def _lint015(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-015"
    ]


def _lint015_json(report):
    data = _report_json(report)
    return [f for f in data["findings"] if f["rule_id"] == "R-LINT-015"]


def _counts(report):
    sev = [field(f, "severity") for f in field(report, "findings")]
    return sev.count("fail"), sev.count("warn"), sev.count("skipped")


def test_ac_lint_034(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    # --- No judge: R-LINT-015 skipped, summary counts consistent ---
    report = spec_linter.lint(None, repo_root)
    n_fail, n_warn, n_skipped = _counts(report)

    entries = _lint015(report)
    assert len(entries) == 1
    assert field(entries[0], "severity") == "skipped"

    # Preconditions of the criterion's corpus: no fails, at least one warn.
    assert n_fail == 0, [
        (field(f, "rule_id"), field(f, "message"))
        for f in field(report, "findings")
        if field(f, "severity") == "fail"
    ]
    assert n_warn >= 1

    assert field(report, "hard_failures") == n_fail
    assert field(report, "warnings") == n_warn
    assert field(report, "skipped") == n_skipped

    summary = _report_json(report)["summary"]
    assert summary["hard_failures"] == n_fail
    assert summary["warnings"] == n_warn
    assert summary["skipped"] == n_skipped

    skipped_json = _lint015_json(report)
    assert len(skipped_json) == 1
    assert skipped_json[0]["severity"] == "skipped"
    assert "rationale" not in skipped_json[0]

    # --- Strict: warn findings count as hard failures ---
    strict_report = spec_linter.lint(None, repo_root, strict=True)
    assert field(strict_report, "hard_failures") == n_warn

    # --- Judge reporting a conflict ---
    calls = []

    def judge_conflict(term, local_text, glossary_text):
        calls.append((term, local_text, glossary_text))
        return (True, "contradicts the glossary")

    conflict_report = spec_linter.lint(None, repo_root, judge=judge_conflict)
    assert calls
    entries = _lint015(conflict_report)
    assert len(entries) == 1
    assert field(entries[0], "severity") == "fail"
    entries_json = _lint015_json(conflict_report)
    assert len(entries_json) == 1
    assert entries_json[0]["severity"] == "fail"
    assert entries_json[0]["rationale"] == "contradicts the glossary"

    # --- Judge reporting consistency: no R-LINT-015 finding ---
    def judge_consistent(term, local_text, glossary_text):
        return (False, "consistent")

    consistent_report = spec_linter.lint(None, repo_root, judge=judge_consistent)
    assert _lint015(consistent_report) == []
    assert _lint015_json(consistent_report) == []

    # --- Judge that cannot judge: skipped, no rationale ---
    def judge_none(term, local_text, glossary_text):
        return None

    none_report = spec_linter.lint(None, repo_root, judge=judge_none)
    entries = _lint015(none_report)
    assert len(entries) == 1
    assert field(entries[0], "severity") == "skipped"
    entries_json = _lint015_json(none_report)
    assert len(entries_json) == 1
    assert entries_json[0]["severity"] == "skipped"
    assert "rationale" not in entries_json[0]