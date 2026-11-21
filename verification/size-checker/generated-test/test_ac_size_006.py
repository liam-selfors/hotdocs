# hotdocs-criterion: sha256:93fff063b19ae9748e2f4be27f38f209ca09cf81eb74cfb6603fb17b98fe4ef1
import re
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


DEP_SLUGS = ["dep-" + str(i).zfill(2) for i in range(1, 12)]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, depends_on):
    lines = [
        "---",
        "id: " + comp_id,
        "title: " + title,
        "status: draft",
        "owners: [team-a]",
    ]
    if depends_on:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    lines.append("sealed: true")
    lines.append("source_path: legacy/" + comp_id + "/")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("A small fixture component.")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- In scope: fixture behavior.")
    lines.append("")
    lines.append("## Definitions")
    lines.append("")
    lines.append("None.")
    lines.append("")
    lines.append("## Behavior")
    lines.append("")
    lines.append("See `requirements/`.")
    lines.append("")
    lines.append("## Interfaces")
    lines.append("")
    lines.append("See `interface/`.")
    lines.append("")
    lines.append("## Data")
    lines.append("")
    lines.append("See `interface/data/`.")
    lines.append("")
    lines.append("## Acceptance criteria")
    lines.append("")
    lines.append("See `acceptance/`.")
    lines.append("")
    lines.append("## Non-functional constraints")
    lines.append("")
    lines.append("See `constraints.md`.")
    lines.append("")
    lines.append("## Open questions")
    lines.append("")
    lines.append("## Change log")
    lines.append("")
    lines.append("- Created.")
    lines.append("")
    return "\n".join(lines)


def _requirement(rid):
    return "# " + rid + "\n\n**" + rid + "** — The component MUST do a thing.\n"


def _acceptance(acid, rid):
    return (
        "# " + acid + "\n\n"
        "Covers: " + rid + "\n"
        "Kind: llm-judge\n\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n"
    )


def _build_corpus(repo_root):
    comps = repo_root / "specs" / "components"

    hub = comps / "hub"
    _write(hub / "component.md", _component_md("comp-hub", "Hub", []))
    _write(hub / "requirements" / "R-HUB-001.md", _requirement("R-HUB-001"))
    for i in range(1, 27):
        acid = "AC-HUB-" + str(i).zfill(3)
        _write(hub / "acceptance" / (acid + ".md"), _acceptance(acid, "R-HUB-001"))
    for i in range(1, 7):
        gid = "G-HUB-" + str(i).zfill(3)
        _write(
            hub / "interface" / "guarantees" / (gid + ".md"),
            "# " + gid + "\n\nThe hub MUST behave consistently.\n",
        )
    _write(hub / "constraints.md", "# Constraints\n\nNone.\n")

    for slug in DEP_SLUGS:
        d = comps / slug
        tag = slug.upper()
        rid = "R-" + tag + "-001"
        acid = "AC-" + tag + "-001"
        _write(d / "component.md", _component_md("comp-" + slug, "Dep " + slug, ["comp-hub"]))
        _write(d / "requirements" / (rid + ".md"), _requirement(rid))
        _write(d / "acceptance" / (acid + ".md"), _acceptance(acid, rid))
        _write(d / "constraints.md", "# Constraints\n\nNone.\n")


def _is_hub(finding):
    f = str(field(finding, "file")).replace("\\", "/")
    msg = str(field(finding, "message"))
    return f.startswith("specs/components/hub/") or "comp-hub" in msg


def _is_dep(finding):
    f = str(field(finding, "file")).replace("\\", "/")
    msg = str(field(finding, "message"))
    for slug in DEP_SLUGS:
        if f.startswith("specs/components/" + slug + "/"):
            return True
        if "comp-" + slug in msg:
            return True
    return False


def test_ac_size_006_hub_gets_guarantee_acceptance_fan_in_warnings(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    size_findings = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    hub_findings = [f for f in size_findings if _is_hub(f)]

    def has(dimension, number):
        pat = re.compile(r"(?<!\d)" + str(number) + r"(?!\d)")
        for f in hub_findings:
            msg = str(field(f, "message"))
            if dimension in msg and pat.search(msg) and field(f, "severity") == "warn":
                return True
        return False

    assert has("guarantee_count", 6), [field(f, "message") for f in size_findings]
    assert has("acceptance_count", 26), [field(f, "message") for f in size_findings]
    assert has("fan_in", 11), [field(f, "message") for f in size_findings]

    for f in size_findings:
        msg = str(field(f, "message"))
        if "fan_in" in msg or "fan_out" in msg:
            assert not _is_dep(f), (field(f, "file"), msg)