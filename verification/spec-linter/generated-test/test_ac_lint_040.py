# hotdocs-criterion: sha256:d6f8d571f2928c199e93c25e1513bd68da0efb8405948d6610381e91b102e0b8
"""AC-LINT-040 (covers R-LINT-034): asset-kind findings for a component's `assets`."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** — a thing used in tests.\n",
    )

    component_md = (
        "---\n"
        "id: comp-web\n"
        "title: Web\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/web/\n"
        "assets: [nosuchkind-x9:a.js, demo:b.js]\n"
        "---\n"
        "\n"
        "# Web\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Serves a small web page for tests.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the page.\n"
        "- Out of scope: everything else.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
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
    _write(specs / "components" / "web" / "component.md", component_md)

    _write(
        specs / "components" / "web" / "requirements" / "R-WEB-001.md",
        "# R-WEB-001\n"
        "\n"
        "**R-WEB-001** — The page MUST render a greeting.\n",
    )
    _write(
        specs / "components" / "web" / "acceptance" / "AC-WEB-001.md",
        "# AC-WEB-001\n"
        "\n"
        "Covers: R-WEB-001\n"
        "Kind: generated-test\n"
        "\n"
        "The page renders a greeting.\n",
    )
    _write(
        specs / "components" / "web" / "constraints.md",
        "# Constraints\n"
        "\n"
        "- None beyond the defaults.\n",
    )

    # Seven sections except: "## Surface" absent, and "## Strength check"
    # followed directly by "## Test author guidance" (empty section).
    definition = (
        "---\n"
        "id: arch-asset-kind-demo\n"
        "title: Asset Kind demo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Asset kind demo\n"
        "\n"
        "## Layout\n"
        "\n"
        "One demo file at path.\n"
        "\n"
        "## Environment\n"
        "\n"
        "No programs needed.\n"
        "\n"
        "## Running criteria\n"
        "\n"
        "asset_runner takes an entry point and arguments.\n"
        "\n"
        "## Strength check\n"
        "## Test author guidance\n"
        "\n"
        "Call asset_runner from tests.\n"
        "\n"
        "## Generator guidance\n"
        "\n"
        "Write a demo file.\n"
    )
    _write(specs / "architecture" / "asset-kind-demo.md", definition)


def test_ac_lint_040_asset_kind_findings_in_order(tmp_path):
    repo_root = Path(tmp_path) / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)

    target_file = "specs/components/web/component.md"
    findings = [
        f
        for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-034"
        and str(field(f, "file")).replace("\\", "/") == target_file
    ]

    for f in findings:
        assert field(f, "severity") == "fail"

    messages = [field(f, "message") for f in findings]
    assert messages == [
        "asset kind 'nosuchkind-x9' has no definition",
        "asset kind 'demo' definition lacks section 'Surface'",
        "asset kind 'demo' definition has empty section 'Strength check'",
        "asset kind 'demo' is defined in this repository; depends_on must list comp-kind-demo",
    ]