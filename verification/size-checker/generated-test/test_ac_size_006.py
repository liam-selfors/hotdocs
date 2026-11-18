# hotdocs-criterion: sha256:523b8f6fa2c9a569466b26fc8ea5196e01b4257ce58439391295eecb80227d17
import re
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(comp_id, title, slug, depends_on):
    text = "---\n"
    text += "id: " + comp_id + "\n"
    text += "title: " + title + "\n"
    text += "status: draft\n"
    text += "owners: [team]\n"
    if depends_on:
        text += "depends_on: [" + ", ".join(depends_on) + "]\n"
    text += "sealed: true\n"
    text += "source_path: legacy/" + slug + "/\n"
    text += "---\n\n"
    text += "# " + title + "\n\n"
    text += "## Purpose\n\nA small fixture component.\n\n"
    text += "## Scope\n\n- In scope: fixture behavior.\n\n"
    text += "## Definitions\n\nNone.\n\n"
    text += "## Behavior\n\nSee `requirements/`.\n\n"
    text += "## Interfaces\n\nSee `interface/`.\n\n"
    text += "## Data\n\nSee `interface/data/`.\n\n"
    text += "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
    text += "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
    text += "## Open questions\n\n"
    text += "## Change log\n\n- Created.\n"
    return text


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n\n- **Fixture** — a test fixture term.\n")

    hub = specs / "components" / "hub"
    write(hub / "component.md", component_md("comp-hub", "Hub", "hub", []))
    write(
        hub / "requirements" / "R-HUB-001.md",
        "# R-HUB-001\n\n**R-HUB-001** — The hub MUST answer requests.\n",
    )
    for i in range(1, 7):
        gid = "G-HUB-" + str(i).zfill(3)
        write(
            hub / "interface" / "guarantees" / (gid + ".md"),
            "# " + gid + "\n\n**" + gid + "** — The hub MUST keep promise " + str(i) + ".\n",
        )
    for i in range(1, 27):
        acid = "AC-HUB-" + str(i).zfill(3)
        write(
            hub / "acceptance" / (acid + ".md"),
            "# " + acid + "\n\nCovers: R-HUB-001\nKind: generated-test\n\n"
            "```gherkin\nGiven a request\nWhen the hub runs\nThen it answers\n```\n",
        )

    for i in range(1, 12):
        slug = "leaf-" + str(i).zfill(2)
        write(
            specs / "components" / slug / "component.md",
            component_md("comp-" + slug, "Leaf " + str(i), slug, ["comp-hub"]),
        )


def has_number(message, number):
    return re.search(r"(?<!\d)" + str(number) + r"(?!\d)", message) is not None


def test_ac_size_006_hub_guarantee_acceptance_fan_in_warns(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    size_findings = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]

    hub_findings = [
        f for f in size_findings
        if str(field(f, "file")).replace("\\", "/").startswith("specs/components/hub/")
    ]
    hub_warns = [f for f in hub_findings if field(f, "severity") == "warn"]

    for dimension, number in (
        ("guarantee_count", 6),
        ("acceptance_count", 26),
        ("fan_in", 11),
    ):
        matching = [
            f for f in hub_warns
            if dimension in str(field(f, "message"))
            and has_number(str(field(f, "message")), number)
        ]
        assert matching, (
            "expected a warn R-SIZE-001 finding for comp-hub naming "
            + dimension + " with " + str(number) + "; got "
            + repr([(field(f, "severity"), field(f, "message")) for f in hub_findings])
        )
        for f in matching:
            assert isinstance(field(f, "line"), int)

    leaf_findings = [
        f for f in size_findings
        if str(field(f, "file")).replace("\\", "/").startswith("specs/components/leaf-")
    ]
    for f in leaf_findings:
        message = str(field(f, "message"))
        assert "fan_in" not in message and "fan_out" not in message, (
            "unexpected fan finding for a leaf component: " + repr(message)
        )