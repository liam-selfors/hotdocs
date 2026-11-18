# hotdocs-criterion: sha256:61e43e9b7f6f5ac81d42b04f255164349f421c73373dfef7d9886ebaf2b7b7eb
"""AC-LINT-011b — covers R-LINT-011.

Given a component's Definitions section whose entry for a glossary term adds
genuinely new, component-specific nuance with low textual overlap against the
glossary's definition, when hotdocs lint runs against the component, then the
report contains no R-LINT-011 finding (a permitted delta, not a redefinition).

A sibling control (a near-verbatim restatement of the same glossary entry)
confirms the fixture's Definitions entry is actually recognised by the
R-LINT-011 check, so the negative assertion is not vacuous.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

import spec_linter


GLOSSARY_TERM = "Blast radius"
GLOSSARY_DEFINITION = (
    "the minimal set of components `impact-analyzer` determines need\n"
    "  regeneration/re-verification for a given spec change."
)

# Genuinely new, component-specific nuance; deliberately shares essentially
# no tokens with the glossary definition above.
DELTA_DEFINITION = (
    "here additionally includes every sealed legacy wrapper whose\n"
    "  characterization fixtures reference touched vocabulary files, counted\n"
    "  once per wrapper even when several fixtures overlap."
)


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(root: Path, definitions_text: str) -> None:
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this synthetic fixture corpus.\n"
        "\n"
        f"- **{GLOSSARY_TERM}** — {GLOSSARY_DEFINITION}\n"
        "- **Gate** — one verification step in the pipeline.\n",
    )

    comp_dir = root / "specs" / "components" / "widget"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/widget\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Wraps a small legacy widget so its behavior is traceable.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the widget wrapper.\n"
        "- Out of scope: everything else.\n"
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
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — The widget MUST match existing behavior.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the legacy widget\n"
        "When it is exercised\n"
        "Then it behaves as before\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "- None beyond matching existing behavior.\n",
    )


def _findings(report):
    findings = _get(report, "findings", None)
    if findings is None:
        return []
    return list(findings)


def _lint_findings_for(definitions_text: str):
    tmp = Path(tempfile.mkdtemp(prefix="ac_lint_011b_"))
    try:
        _build_repo(tmp, definitions_text)
        report = spec_linter.lint(None, tmp)
        assert report is not None, "lint() returned None instead of a LintReport"
        return _findings(report)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _r_lint_011(findings):
    return [f for f in findings if _get(f, "rule_id") == "R-LINT-011"]


def test_low_overlap_delta_is_not_flagged_as_redefinition():
    findings = _lint_findings_for(DELTA_DEFINITION)
    hits = _r_lint_011(findings)
    assert hits == [], (
        "A Definitions entry adding genuinely new, low-overlap nuance to a "
        "glossary term is a permitted delta and must not produce an "
        "R-LINT-011 finding; got: "
        + repr([(_get(f, "file"), _get(f, "line"), _get(f, "message")) for f in hits])
    )


def test_low_overlap_delta_not_flagged_even_in_strict_mode():
    tmp = Path(tempfile.mkdtemp(prefix="ac_lint_011b_strict_"))
    try:
        _build_repo(tmp, DELTA_DEFINITION)
        report = spec_linter.lint(None, tmp, strict=True)
        hits = _r_lint_011(_findings(report))
        assert hits == [], (
            "strict mode must not turn a permitted low-overlap delta into an "
            "R-LINT-011 finding; got: "
            + repr([_get(f, "message") for f in hits])
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_control_near_verbatim_restatement_is_flagged():
    # Control: the same fixture, but the Definitions entry restates the
    # glossary definition verbatim. This proves the entry is actually seen by
    # the R-LINT-011 check, so the negative test above is meaningful.
    findings = _lint_findings_for(GLOSSARY_DEFINITION)
    hits = _r_lint_011(findings)
    assert hits, (
        "control fixture: a verbatim restatement of the glossary definition "
        "must produce an R-LINT-011 finding; findings were: "
        + repr([(_get(f, "rule_id"), _get(f, "message")) for f in findings])
    )
    assert any(_get(f, "severity") == "fail" for f in hits), (
        "R-LINT-011 restatement finding must be fail-severity; got: "
        + repr([_get(f, "severity") for f in hits])
    )
    assert any(
        "components/widget" in str(_get(f, "file", "")).replace("\\", "/")
        for f in hits
    ), (
        "R-LINT-011 finding should be reported against the widget component; "
        "got files: " + repr([_get(f, "file") for f in hits])
    )