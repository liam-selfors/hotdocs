import json
from pathlib import Path

import spec_linter


GLOSSARY_TERM = "Widget"
GLOSSARY_DEFINITION = (
    "a reusable rendering unit that the dashboard assembles from declarative "
    "configuration files at startup and caches in memory for subsequent "
    "requests until the configuration changes"
)


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(root: Path, definitions_entry_text: str) -> Path:
    specs = root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this test corpus.\n"
        "\n"
        f"- **{GLOSSARY_TERM}** — {GLOSSARY_DEFINITION}.\n"
        "- **Gadget** — a small helper object owned by exactly one widget.\n",
    )

    comp_dir = specs / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Renders widgets for the dashboard.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: rendering widgets.\n"
        "- Out of scope: storing configuration.\n"
        "\n"
        "## Definitions\n"
        "\n"
        f"- **{GLOSSARY_TERM}** — {definitions_entry_text}\n"
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
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The component MUST render every configured widget.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a configured widget\n"
        "When the dashboard renders\n"
        "Then the widget is rendered\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Rendering MUST complete within 100 ms, measured by a benchmark.\n",
    )
    return root


def _findings(report):
    findings = _get(report, "findings", None)
    assert findings is not None, "LintReport has no findings field"
    return list(findings)


def _lint_011(report):
    return [f for f in _findings(report) if _get(f, "rule_id") == "R-LINT-011"]


def test_verbatim_copy_of_glossary_definition_fails_r_lint_011(tmp_path):
    root = _build_corpus(tmp_path / "repo", GLOSSARY_DEFINITION + ".")
    report = spec_linter.lint(None, root)

    hits = _lint_011(report)
    assert hits, "expected an R-LINT-011 finding for a verbatim glossary copy"
    fails = [f for f in hits if _get(f, "severity") == "fail"]
    assert fails, f"expected fail severity for R-LINT-011, got {[_get(f, 'severity') for f in hits]}"

    files = [str(_get(f, "file") or "").replace("\\", "/") for f in fails]
    assert any(p.endswith("specs/components/foo/component.md") for p in files), files

    hard_failures = _get(report, "hard_failures")
    if hard_failures is None:
        summary = _get(report, "summary") or {}
        hard_failures = _get(summary, "hard_failures")
    assert hard_failures is not None and hard_failures >= 1


def test_near_verbatim_copy_one_word_changed_fails_r_lint_011(tmp_path):
    near = GLOSSARY_DEFINITION.replace("dashboard", "console") + "."
    assert near.rstrip(".") != GLOSSARY_DEFINITION
    root = _build_corpus(tmp_path / "repo", near)
    report = spec_linter.lint(None, root)

    fails = [f for f in _lint_011(report) if _get(f, "severity") == "fail"]
    assert fails, "expected a fail-severity R-LINT-011 finding for a near-verbatim copy"


def test_genuine_delta_does_not_trigger_r_lint_011(tmp_path):
    delta = (
        "here, only plugin-supplied entries loaded via the extensions folder "
        "count; built-in ones are ignored entirely."
    )
    root = _build_corpus(tmp_path / "repo", delta)
    report = spec_linter.lint(None, root)

    assert _lint_011(report) == [], (
        "a genuine delta must not be reported under R-LINT-011"
    )


def test_cli_reports_r_lint_011_fail_in_json(tmp_path, capsys):
    root = _build_corpus(tmp_path / "repo", GLOSSARY_DEFINITION + ".")
    code = spec_linter.main([f"--repo-root={root}", "--format=json"])
    out = capsys.readouterr().out

    assert code == 1
    data = json.loads(out)
    findings = data.get("findings", [])
    assert any(
        f.get("rule_id") == "R-LINT-011" and f.get("severity") == "fail"
        for f in findings
    ), findings