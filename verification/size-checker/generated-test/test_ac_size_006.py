# hotdocs-criterion: sha256:597fdd3c1a2cb6b1aafef249c7d084ad6ff1827c6c1d1204c10fbbc288818338
"""AC-SIZE-006: comp-hub exceeding guarantee_count, acceptance_count and fan_in
gets warn R-SIZE-001 findings; the eleven spokes get no fan_in/fan_out finding."""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, depends_on):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug + " component\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# " + slug + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component used for size checks.\n"
    )


def requirement_md(rid):
    return "# " + rid + "\n\n**" + rid + "** — The component MUST respond.\n"


def acceptance_md(acid, rid):
    return (
        "# " + acid + "\n"
        + "\n"
        + "Covers: " + rid + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given a request\n"
        + "When it runs\n"
        + "Then it responds\n"
        + "```\n"
    )


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n\n- **Fixture** — a test corpus.\n")

    # comp-hub
    hub = specs / "components" / "hub"
    write(hub / "component.md", component_md("hub", []))
    write(hub / "requirements" / "R-HUB-001.md", requirement_md("R-HUB-001"))
    for i in range(1, 7):
        gid = "G-HUB-" + str(i).zfill(3)
        write(
            hub / "interface" / "guarantees" / (gid + ".md"),
            "# " + gid + "\n\nThe hub guarantees property " + str(i) + ".\n",
        )
    for i in range(1, 27):
        acid = "AC-HUB-" + str(i).zfill(3)
        write(hub / "acceptance" / (acid + ".md"), acceptance_md(acid, "R-HUB-001"))

    # eleven spokes depending on comp-hub
    spoke_names = []
    for i in range(1, 12):
        slug = "spoke-" + str(i).zfill(2)
        spoke_names.append(slug)
        upper = "SPOKE" + str(i).zfill(2)
        d = specs / "components" / slug
        write(d / "component.md", component_md(slug, ["comp-hub"]))
        rid = "R-" + upper + "-001"
        acid = "AC-" + upper + "-001"
        write(d / "requirements" / (rid + ".md"), requirement_md(rid))
        write(d / "acceptance" / (acid + ".md"), acceptance_md(acid, rid))
    return spoke_names


def test_ac_size_006(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    spoke_names = build_fixture(repo_root)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    size001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    hub_findings = [f for f in size001 if field(f, "message").startswith("hub: ")]

    expected = [
        "hub: guarantee_count is 6, above the warn threshold of 5 (specs/architecture/size-caps.md)",
        "hub: acceptance_count is 26, above the warn threshold of 25 (specs/architecture/size-caps.md)",
        "hub: fan_in is 11, above the warn threshold of 10 (specs/architecture/size-caps.md)",
    ]
    hub_messages = [field(f, "message") for f in hub_findings]
    for msg in expected:
        assert msg in hub_messages, (msg, hub_messages)
        matching = [f for f in hub_findings if field(f, "message") == msg]
        for f in matching:
            assert field(f, "severity") == "warn"
            assert isinstance(field(f, "line"), int)

    for slug in spoke_names:
        prefix = slug + ": "
        for f in size001:
            msg = field(f, "message")
            if msg.startswith(prefix):
                assert "fan_in" not in msg, msg
                assert "fan_out" not in msg, msg