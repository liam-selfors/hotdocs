# hotdocs-criterion: sha256:61e43e9b7f6f5ac81d42b04f255164349f421c73373dfef7d9886ebaf2b7b7eb
"""AC-LINT-011b: a Definitions entry that adds genuinely new, low-overlap
nuance to a glossary term is a permitted delta, not a redefinition, so
the lint report carries no R-LINT-011 finding."""

import json
from pathlib import Path

import spec_linter


TERM = "Widget frobnication"

GLOSSARY_TEXT = (
    "the process by which a widget's internal counters are reset to zero "
    "before each batch run begins, so that every run starts from a clean "
    "baseline."
)

# Genuinely new, component-specific nuance with low token overlap.
DELTA_TEXT = (
    "Here, frobnication additionally locks our shared ledger file, letting "
    "concurrent readers observe one stable snapshot while it proceeds."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, definition_text):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **" + TERM + "** \u2014 " + GLOSSARY_TEXT + "\n"
        "- **Other term** \u2014 an unrelated entry used only as padding.\n",
    )
    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
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
        "Foo frobnicates widgets for its callers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: frobnicating widgets.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "- **" + TERM + "** \u2014 " + definition_text + "\n"
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
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 Foo MUST frobnicate a widget when asked.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When foo frobnicates it\n"
        "Then the widget is frobnicated\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- None beyond the defaults.\n",
    )


def _lint011(report):
    return [
        f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-011"
    ]


def test_low_overlap_delta_has_no_r_lint_011_finding(tmp_path):
    _build_corpus(tmp_path, DELTA_TEXT)
    report = spec_linter.lint(None, tmp_path)
    found = _lint011(report)
    assert found == [], "unexpected R-LINT-011 findings: " + repr(found)


def test_low_overlap_delta_cli_json_has_no_r_lint_011_finding(tmp_path, capsys):
    _build_corpus(tmp_path, DELTA_TEXT)
    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    assert code in (0, 1)
    out = capsys.readouterr().out
    doc = json.loads(out)
    rule_ids = [f["rule_id"] for f in doc["findings"]]
    assert "R-LINT-011" not in rule_ids


def test_control_verbatim_restatement_is_flagged(tmp_path):
    # Control: the same fixture with the glossary text restated verbatim
    # must trigger R-LINT-011, proving the negative result above is not
    # merely the entry going unread.
    _build_corpus(tmp_path, GLOSSARY_TEXT)
    report = spec_linter.lint(None, tmp_path)
    found = _lint011(report)
    assert found, "verbatim restatement was not flagged by R-LINT-011"
    assert all(field(f, "severity") == "fail" for f in found)