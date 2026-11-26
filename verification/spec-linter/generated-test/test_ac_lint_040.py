# hotdocs-criterion: sha256:d9f59b98b07c3c427a235b67d7ea207b69b4dd0b3509af83750f56e62c6d210c
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_LINES = [
    "---",
    "id: comp-web",
    "title: Web",
    "status: draft",
    "owners: [web-team]",
    "depends_on: []",
    "assets: [nosuchkind-x9:a.js, demo:b.js]",
    "sealed: true",
    "source_path: legacy/web/",
    "---",
    "",
    "# Web",
    "",
    "## Purpose",
    "",
    "Serves the web front end.",
    "",
    "## Scope",
    "",
    "- In scope: the web front end.",
    "",
    "## Definitions",
    "",
    "None.",
    "",
    "## Behavior",
    "",
    "See `requirements/`.",
    "",
    "## Interfaces",
    "",
    "See `interface/`.",
    "",
    "## Data",
    "",
    "See `interface/data/`.",
    "",
    "## Acceptance criteria",
    "",
    "See `acceptance/`.",
    "",
    "## Non-functional constraints",
    "",
    "See `constraints.md`.",
    "",
    "## Open questions",
    "",
    "## Change log",
    "",
    "- Initial draft.",
    "",
]

ASSETS_LINE = COMPONENT_LINES.index("assets: [nosuchkind-x9:a.js, demo:b.js]") + 1

DEFINITION_LINES = [
    "---",
    "id: arch-asset-kind-demo",
    "title: Asset Kind demo",
    "status: draft",
    "owners: [pipeline-team]",
    "depends_on: []",
    "---",
    "",
    "# Asset Kind demo",
    "",
    "## Layout",
    "",
    "One demo file.",
    "",
    "## Environment",
    "",
    "No programs needed.",
    "",
    "## Running criteria",
    "",
    "asset_runner takes an entry point and returns a value.",
    "",
    "## Strength check",
    "## Test author guidance",
    "",
    "Build fixtures and call asset_runner.",
    "",
    "## Generator guidance",
    "",
    "Follow demo conventions.",
    "",
]


def build_repo(repo_root: Path) -> None:
    specs = repo_root / "specs"
    comp_dir = specs / "components" / "web"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text("\n".join(COMPONENT_LINES), encoding="utf-8")
    arch = specs / "architecture"
    arch.mkdir(parents=True)
    (arch / "asset-kind-demo.md").write_text("\n".join(DEFINITION_LINES), encoding="utf-8")
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Web** — the web front end.\n", encoding="utf-8"
    )


def test_ac_lint_040(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")

    relevant = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-034"
        and field(f, "severity") == "fail"
        and field(f, "file") == "specs/components/web/component.md"
    ]
    messages = [field(f, "message") for f in relevant]

    assert messages == [
        "asset kind 'nosuchkind-x9' has no definition; run hotdocs kind new nosuchkind-x9",
        "asset kind 'demo' definition lacks section 'Surface'",
        "asset kind 'demo' definition has empty section 'Strength check'",
        "asset kind 'demo' is defined in this repository; depends_on must list comp-kind-demo",
    ]
    for f in relevant:
        assert field(f, "line") == ASSETS_LINE