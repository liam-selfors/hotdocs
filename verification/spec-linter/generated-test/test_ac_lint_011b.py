import json
from pathlib import Path

import spec_linter


GLOSSARY_TERM = "Widget frobnicator"

GLOSSARY_DEFINITION = (
    "a pipeline stage that converts raw widget payloads into normalized "
    "frobnication records for downstream storage and later retrieval."
)

# Genuinely new, component-specific nuance: near-zero token overlap with the
# glossary's own definition text (well under the 0.8 threshold).
LOCAL_DELTA_TEXT = (
    "Here, additionally capped at three concurrent sessions per tenant; on "
    "timeout it retries exactly once before surfacing an error to callers."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root: Path, definitions_text: str) -> Path:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus.\n"
        "\n"
        f"- **{GLOSSARY_TERM}** — {GLOSSARY_DEFINITION}\n"
        "- **Gate** — one verification step in the pipeline.\n",
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
        "- Out of scope: storing them.\n"
        "\n"
        "## Definitions\n"
        "\n"
        f"- **{GLOSSARY_TERM}** — {definitions_text}\n"
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
        "**R-FOO-001** — Foo MUST frobnicate every widget it is given.\n",
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
        "When foo runs\n"
        "Then the widget is frobnicated\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Frobnicates a widget in under 1 second, measured by a timer.\n",
    )
    return repo_root


def _rule_ids(report):
    findings = field(report, "findings")
    return [field(f, "rule_id") for f in findings]


def test_low_overlap_definitions_delta_is_not_flagged_by_r_lint_011(tmp_path):
    repo_root = _build_repo(tmp_path / "repo", LOCAL_DELTA_TEXT)

    report = spec_linter.lint(None, repo_root)

    rule_ids = _rule_ids(report)
    assert "R-LINT-011" not in rule_ids, (
        "a genuinely new, low-overlap Definitions delta must not be reported "
        f"as a redefinition; findings: {rule_ids}"
    )


def test_low_overlap_delta_not_flagged_via_cli_json(tmp_path, capsys):
    repo_root = _build_repo(tmp_path / "repo", LOCAL_DELTA_TEXT)

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out

    assert code in (0, 1)
    doc = json.loads(out)
    rule_ids = [f["rule_id"] for f in doc["findings"]]
    assert "R-LINT-011" not in rule_ids, rule_ids


def test_control_near_verbatim_restatement_is_flagged(tmp_path):
    # Sanity control: the same fixture shape, with the glossary definition
    # restated verbatim, does trigger R-LINT-011 -- so the absence asserted
    # above reflects the low overlap, not a fixture the linter never parsed.
    repo_root = _build_repo(tmp_path / "repo", GLOSSARY_DEFINITION)

    report = spec_linter.lint(None, repo_root)

    findings = field(report, "findings")
    hits = [f for f in findings if field(f, "rule_id") == "R-LINT-011"]
    assert hits, f"expected an R-LINT-011 finding; got {_rule_ids(report)}"
    assert all(field(f, "severity") == "fail" for f in hits)