# hotdocs-criterion: sha256:523b8f6fa2c9a569466b26fc8ea5196e01b4257ce58439391295eecb80227d17
import re
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_BODY = (
    "# Title\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A small fixture component.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: fixture.\n"
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
    "- Created.\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(comp_id, slug, depends_on=None):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + slug,
        "status: draft",
        "owners: [team]",
        "sealed: true",
        "source_path: legacy/" + slug + "/",
    ]
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.append("---")
    return "\n".join(lines) + "\n" + COMPONENT_BODY


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n\n- **Thing** — a thing.\n")

    hub = specs / "components" / "hub"
    write(hub / "component.md", component_md("comp-hub", "hub"))
    write(
        hub / "requirements" / "R-HUB-001.md",
        "# R-HUB-001\n\n**R-HUB-001** — The hub MUST exist.\n",
    )
    for i in range(1, 7):
        gid = "G-HUB-" + str(i).zfill(3)
        write(
            hub / "interface" / "guarantees" / (gid + ".md"),
            "# " + gid + "\n\nThe hub MUST keep promise " + str(i) + ".\n",
        )
    for i in range(1, 27):
        aid = "AC-HUB-" + str(i).zfill(3)
        write(
            hub / "acceptance" / (aid + ".md"),
            "# " + aid + "\n\n"
            "Covers: R-HUB-001\n"
            "Kind: generated-test\n\n"
            "```gherkin\n"
            "Given a hub\n"
            "When it is checked\n"
            "Then it exists\n"
            "```\n",
        )
    write(hub / "constraints.md", "# Constraints\n\nNone.\n")

    leaves = []
    for i in range(1, 12):
        slug = "leaf-" + str(i).zfill(2)
        leaves.append(slug)
        d = specs / "components" / slug
        write(d / "component.md", component_md("comp-" + slug, slug, ["comp-hub"]))
        write(d / "constraints.md", "# Constraints\n\nNone.\n")
    return leaves


def has_number(message, number):
    return re.search(r"(?<!\d)" + str(number) + r"(?!\d)", message) is not None


def test_ac_size_006_hub_warns_and_leaves_have_no_fan_findings(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    leaves = build_fixture(repo_root)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    size_001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]

    hub_prefix = "specs/components/hub/"
    hub_findings = [
        f
        for f in size_001
        if str(field(f, "file")).replace("\\", "/").startswith(hub_prefix)
    ]
    assert hub_findings, "expected R-SIZE-001 findings for comp-hub, got: " + repr(findings)

    def hub_warn_with(dimension, number):
        for f in hub_findings:
            msg = str(field(f, "message"))
            if (
                field(f, "severity") == "warn"
                and dimension in msg
                and has_number(msg, number)
            ):
                return True
        return False

    assert hub_warn_with("guarantee_count", 6), repr(hub_findings)
    assert hub_warn_with("acceptance_count", 26), repr(hub_findings)
    assert hub_warn_with("fan_in", 11), repr(hub_findings)

    for f in size_001:
        rel = str(field(f, "file")).replace("\\", "/")
        if rel.startswith(hub_prefix):
            continue
        msg = str(field(f, "message"))
        assert "fan_in" not in msg and "fan_out" not in msg, (
            "unexpected fan finding on non-hub file: " + repr(f)
        )

    for slug in leaves:
        prefix = "specs/components/" + slug + "/"
        for f in size_001:
            rel = str(field(f, "file")).replace("\\", "/")
            if rel.startswith(prefix):
                msg = str(field(f, "message"))
                assert "fan_in" not in msg and "fan_out" not in msg, repr(f)