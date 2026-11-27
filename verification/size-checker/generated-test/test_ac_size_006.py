# hotdocs-criterion: sha256:7082b4ae150cd34d4e4d6c1361c26dd3303e0575b9a758625b4268b4ad8c0877
"""AC-SIZE-006: guarantee_count, acceptance_count and fan_in findings for a hub component."""

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
        + "A small fixture component named " + slug + ".\n"
    )


def requirement_md(req_id):
    return "# " + req_id + "\n\n**" + req_id + "** — The component MUST do one small thing.\n"


def acceptance_md(ac_id, req_id):
    return (
        "# " + ac_id + "\n"
        + "\n"
        + "Covers: " + req_id + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given a thing\n"
        + "When it runs\n"
        + "Then it works\n"
        + "```\n"
    )


def guarantee_md(g_id):
    return "# " + g_id + "\n\nThe component guarantees one small property.\n"


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n\n- **Thing** — a fixture term.\n")

    hub = specs / "components" / "hub"
    write(hub / "component.md", component_md("hub", []))
    write(hub / "requirements" / "R-HUB-001.md", requirement_md("R-HUB-001"))
    for i in range(1, 27):
        ac_id = "AC-HUB-" + str(i).zfill(3)
        write(hub / "acceptance" / (ac_id + ".md"), acceptance_md(ac_id, "R-HUB-001"))
    for i in range(1, 7):
        g_id = "G-HUB-" + str(i).zfill(3)
        write(hub / "interface" / "guarantees" / (g_id + ".md"), guarantee_md(g_id))

    leaves = []
    for i in range(1, 12):
        slug = "leaf" + str(i).zfill(2)
        leaves.append(slug)
        tag = "LEAF" + str(i).zfill(2)
        base = specs / "components" / slug
        write(base / "component.md", component_md(slug, ["comp-hub"]))
        req_id = "R-" + tag + "-001"
        ac_id = "AC-" + tag + "-001"
        write(base / "requirements" / (req_id + ".md"), requirement_md(req_id))
        write(base / "acceptance" / (ac_id + ".md"), acceptance_md(ac_id, req_id))
    return leaves


def test_ac_size_006_hub_guarantee_acceptance_and_fan_in(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    leaves = build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size001 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    hub_findings = [f for f in size001 if field(f, "message").startswith("hub: ")]
    hub_messages = [field(f, "message") for f in hub_findings]

    expected = {
        "guarantee_count": "hub: guarantee_count is 6, above the warn threshold of 5 "
        "(specs/architecture/size-caps.md)",
        "acceptance_count": "hub: acceptance_count is 26, above the warn threshold of 25 "
        "(specs/architecture/size-caps.md)",
        "fan_in": "hub: fan_in is 11, above the warn threshold of 10 "
        "(specs/architecture/size-caps.md)",
    }
    for dimension, message in expected.items():
        matching = [f for f in hub_findings if field(f, "message") == message]
        assert matching, (
            "missing R-SIZE-001 finding for " + dimension + "; hub messages: " + repr(hub_messages)
        )
        for f in matching:
            assert field(f, "severity") == "warn"

    for slug in leaves:
        prefix = slug + ": "
        for f in size001:
            message = field(f, "message")
            if not message.startswith(prefix):
                continue
            assert "fan_in" not in message, repr(message)
            assert "fan_out" not in message, repr(message)