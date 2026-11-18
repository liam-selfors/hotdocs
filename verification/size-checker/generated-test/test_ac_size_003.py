# hotdocs-criterion: sha256:c0f32df6bb1b03862a20bd3ebdcc5b6ec3588e67f48caad6da64e523b4fb590b
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-foo]\n"
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
    "- In scope: frobnication.\n"
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
    "- Initial.\n"
)


def long_requirement_text():
    return (
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The tool MUST "
        + " ".join(["frobnicate"] * 607)
        + " widgets.\n"
    )


def short_requirement_text():
    return (
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** — The tool MUST report each widget it frobnicates.\n"
    )


def acceptance_text(ac_id, r_id):
    return (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + r_id + "\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When the tool runs\n"
        "Then the widget is frobnicated\n"
        "```\n"
    )


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    long_text = long_requirement_text()
    short_text = short_requirement_text()
    write(comp / "requirements" / "R-FOO-001.md", long_text)
    write(comp / "requirements" / "R-FOO-002.md", short_text)
    write(comp / "acceptance" / "AC-FOO-001.md", acceptance_text("AC-FOO-001", "R-FOO-001"))
    write(comp / "acceptance" / "AC-FOO-002.md", acceptance_text("AC-FOO-002", "R-FOO-002"))
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    return len(long_text.split()), len(short_text.split())


def test_ac_size_003_per_file_word_count_distinct_from_aggregate(tmp_path):
    repo_root = tmp_path
    long_count, short_count = build_fixture(repo_root)
    assert long_count > 500
    assert short_count < 250

    # Sanity: total component docs stay well under the aggregate caps.
    comp = repo_root / "specs" / "components" / "foo"
    total = 0
    for p in comp.rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            lines = text.splitlines()
            end = lines.index("---", 1)
            text = "\n".join(lines[end + 1:])
        total += len(text.split())
    assert total < 2000

    findings = size_checker.check(Path(repo_root))
    assert isinstance(findings, list)

    long_rel = "specs/components/foo/requirements/R-FOO-001.md"
    short_rel = "specs/components/foo/requirements/R-FOO-002.md"

    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    long_findings = [f for f in size3 if field(f, "file") == long_rel]
    assert len(long_findings) >= 1, findings
    fail_findings = [f for f in long_findings if field(f, "severity") == "fail"]
    assert len(fail_findings) == 1, long_findings
    finding = fail_findings[0]
    assert str(long_count) in field(finding, "message")
    assert isinstance(field(finding, "line"), int)

    short_findings = [f for f in size3 if field(f, "file") == short_rel]
    assert short_findings == [], short_findings

    size1 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    assert size1 == [], size1