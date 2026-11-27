# hotdocs-criterion: sha256:dd7705376247a9e849666b45017b1663d680c80202cde1acf7ff4e25b6e1e4df
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    specs = repo_root / "specs"

    write(
        specs / "architecture" / "target.md",
        "\n".join(
            [
                "---",
                "id: arch-target",
                "title: Target",
                "status: draft",
                "owners: [pipeline-team]",
                "depends_on: []",
                "---",
                "",
                "# Target",
                "",
                "Some intro text.",
                "",
                "## Query surface",
                "",
                "The query surface is described here.",
                "",
            ]
        ),
    )

    comp = specs / "components" / "widget"
    write(
        comp / "component.md",
        "\n".join(
            [
                "---",
                "id: comp-widget",
                "title: Widget",
                "status: draft",
                "owners: [pipeline-team]",
                "depends_on: []",
                "sealed: true",
                "source_path: legacy/widget/",
                "---",
                "",
                "# Widget",
                "",
                "A small fixture component.",
                "",
            ]
        ),
    )

    write(
        comp / "requirements" / "R-WID-001.md",
        "\n".join(
            [
                "# R-WID-001",
                "",
                "**R-WID-001** — The widget MUST answer queries as",
                "`specs/architecture/target.md`'s \"Query surface\" section",
                "describes.",
                "",
            ]
        ),
    )
    write(
        comp / "requirements" / "R-WID-002.md",
        "\n".join(
            [
                "# R-WID-002",
                "",
                "**R-WID-002** — The widget MUST behave as",
                "`specs/architecture/target.md`'s \"Nonexistent Heading\" section",
                "describes.",
                "",
            ]
        ),
    )

    write(
        comp / "acceptance" / "AC-WID-001.md",
        "\n".join(
            [
                "# AC-WID-001",
                "",
                "Covers: R-WID-001",
                "Kind: generated-test",
                "",
                "```gherkin",
                "Given a widget",
                "When it is queried",
                "Then it answers",
                "```",
                "",
            ]
        ),
    )
    write(
        comp / "acceptance" / "AC-WID-002.md",
        "\n".join(
            [
                "# AC-WID-002",
                "",
                "Covers: R-WID-002",
                "Kind: generated-test",
                "",
                "```gherkin",
                "Given a widget",
                "When it runs",
                "Then it behaves",
                "```",
                "",
            ]
        ),
    )


def test_ac_cite_002_only_missing_heading_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)

    cite_002 = [f for f in findings if field(f, "rule_id") == "R-CITE-002"]

    good_rel = "specs/components/widget/requirements/R-WID-001.md"
    bad_rel = "specs/components/widget/requirements/R-WID-002.md"

    def norm(p):
        return str(p).replace("\\", "/")

    good_hits = [f for f in cite_002 if norm(field(f, "file")) == good_rel]
    bad_hits = [f for f in cite_002 if norm(field(f, "file")) == bad_rel]

    assert good_hits == [], "valid 'Query surface' citation was flagged: " + repr(good_hits)
    assert len(bad_hits) >= 1, (
        "missing 'Nonexistent Heading' citation was not flagged: " + repr(findings)
    )

    other = [
        f for f in cite_002 if norm(field(f, "file")) not in (good_rel, bad_rel)
    ]
    assert other == [], "unexpected R-CITE-002 findings: " + repr(other)

    for f in bad_hits:
        assert field(f, "severity") in ("fail", "warn")
        assert isinstance(field(f, "line"), int)
        assert isinstance(field(f, "message"), str)