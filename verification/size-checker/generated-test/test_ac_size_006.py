# hotdocs-criterion: sha256:36fdf03907bb6b2e0483ae07f417ee67f3e0a49fd63b35df9e83cc068f36b457
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, depends_on):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug + "\n"
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
        + "A small fixture component.\n"
    )


def build_fixture(repo_root):
    comps = repo_root / "specs" / "components"

    hub = comps / "hub"
    write(hub / "component.md", component_md("hub", []))
    write(
        hub / "requirements" / "R-HUB-001.md",
        "# R-HUB-001\n\n**R-HUB-001** — The hub MUST exist.\n",
    )
    for i in range(1, 7):
        gid = "G-HUB-" + str(i).zfill(3)
        write(
            hub / "interface" / "guarantees" / (gid + ".md"),
            "# " + gid + "\n\nThe hub guarantees item " + str(i) + ".\n",
        )
    for i in range(1, 27):
        acid = "AC-HUB-" + str(i).zfill(3)
        write(
            hub / "acceptance" / (acid + ".md"),
            "# " + acid + "\n"
            + "\n"
            + "Covers: R-HUB-001\n"
            + "Kind: generated-test\n"
            + "\n"
            + "```gherkin\n"
            + "Given the hub\n"
            + "When it is checked\n"
            + "Then it exists\n"
            + "```\n",
        )

    others = []
    for i in range(1, 12):
        slug = "dep" + str(i).zfill(2)
        others.append(slug)
        write(comps / slug / "component.md", component_md(slug, ["comp-hub"]))
    return others


def test_ac_size_006(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    others = build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    hub_findings = [f for f in size001 if field(f, "message").startswith("hub: ")]
    hub_by_message = {field(f, "message"): f for f in hub_findings}

    expected = [
        "hub: guarantee_count is 6, above the warn threshold of 5 (specs/architecture/size-caps.md)",
        "hub: acceptance_count is 26, above the warn threshold of 25 (specs/architecture/size-caps.md)",
        "hub: fan_in is 11, above the warn threshold of 10 (specs/architecture/size-caps.md)",
    ]
    for msg in expected:
        assert msg in hub_by_message, (msg, [field(f, "message") for f in findings])
        assert field(hub_by_message[msg], "severity") == "warn"

    for slug in others:
        for f in size001:
            msg = field(f, "message")
            if msg.startswith(slug + ": "):
                assert "fan_in" not in msg, msg
                assert "fan_out" not in msg, msg