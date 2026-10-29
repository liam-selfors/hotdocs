"""AC-ASSEMBLE-003 (covers R-ASSEMBLE-003).

Given a component with uses_var: [VAR-FOO-URL]
When assemble runs for that component
Then the resulting SpecBundle's vars field contains VAR-FOO-URL's full
  declaration content
"""

from pathlib import Path

import spec_bundle_assembler


VAR_ID = "VAR-FOO-URL"

# Distinctive tokens for each part of the var declaration R-ASSEMBLE-003
# requires to be carried in full: name, type, required/optional,
# description, sensitivity.
VAR_NAME_TOKEN = "FOO_SERVICE_URL"
VAR_TYPE_TOKEN = "url-string-type-marker"
VAR_REQUIRED_TOKEN = "required-marker-yes"
VAR_DESCRIPTION_TOKEN = (
    "Base URL of the upstream foo service, distinctive-description-7c41."
)
VAR_SENSITIVITY_TOKEN = "sensitivity-marker-internal"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "---\n"
        "id: glossary\n"
        "title: Glossary\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# Glossary\n"
        "\n"
        "- **Foo** — the fixture component used by this test.\n",
    )

    _write(
        specs / "vars" / f"{VAR_ID}.md",
        "---\n"
        f"id: {VAR_ID}\n"
        "title: Foo service URL\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        f"# {VAR_ID}\n"
        "\n"
        f"- **Name:** `{VAR_NAME_TOKEN}`\n"
        f"- **Type:** {VAR_TYPE_TOKEN}\n"
        f"- **Required/optional:** {VAR_REQUIRED_TOKEN}\n"
        f"- **Description:** {VAR_DESCRIPTION_TOKEN}\n"
        f"- **Sensitivity:** {VAR_SENSITIVITY_TOKEN}\n",
    )

    comp_dir = specs / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [tester]\n"
        "sealed: true\n"
        "source_path: legacy/foo\n"
        "depends_on: []\n"
        f"uses_var: [{VAR_ID}]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Fixture component that reads the foo service URL.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — Foo MUST read the foo service URL from "
        f"`{VAR_ID}`.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        f"Given {VAR_ID} is set\n"
        "When foo starts\n"
        "Then foo uses that URL\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo() -> None\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None beyond the corpus defaults.\n",
    )


def _hard_fail_findings(report):
    findings = _get(report, "findings")
    if findings is None and isinstance(report, (list, tuple)):
        findings = report
    hard = []
    for finding in findings or []:
        severity = (
            _get(finding, "severity")
            or _get(finding, "level")
            or _get(finding, "kind")
        )
        if str(severity).lower().replace("_", "-") in ("hard-fail", "hard", "error"):
            hard.append(finding)
    return hard


def _assert_fixture_lint_clean(repo_root: Path) -> None:
    try:
        import spec_linter
    except ImportError:
        return
    lint = getattr(spec_linter, "lint", None)
    if lint is None:
        return
    report = lint(None, repo_root)
    hard = _hard_fail_findings(report)
    assert hard == [], f"fixture is not lint-clean: {hard!r}"


def test_ac_assemble_003_vars_contains_full_declaration(tmp_path):
    repo_root = tmp_path
    _build_fixture(repo_root)
    _assert_fixture_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    assert _get(bundle, "component_id") == "comp-foo"

    vars_field = _get(bundle, "vars")
    assert vars_field is not None, "SpecBundle has no vars field"
    assert VAR_ID in vars_field, (
        f"{VAR_ID} missing from SpecBundle.vars: {vars_field!r}"
    )

    declaration = vars_field[VAR_ID]
    text = declaration if isinstance(declaration, str) else str(declaration)

    for label, token in (
        ("name", VAR_NAME_TOKEN),
        ("type", VAR_TYPE_TOKEN),
        ("required/optional", VAR_REQUIRED_TOKEN),
        ("description", VAR_DESCRIPTION_TOKEN),
        ("sensitivity", VAR_SENSITIVITY_TOKEN),
    ):
        assert token in text, (
            f"{VAR_ID}'s {label} ({token!r}) missing from bundle vars "
            f"entry: {text!r}"
        )