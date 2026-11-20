# hotdocs-criterion: sha256:54147b82e92d8c25f73e15f59da4eb09956f7b552bb5e744cbfe1e09425a87eb
from pathlib import Path

import citation_checker


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
    "owners: [alice]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small thing for testing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the small thing.\n"
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
    "- Initial version.\n"
)

ARCH_MD = (
    "---\n"
    "id: graph-query-engine\n"
    "title: Graph query engine\n"
    "status: draft\n"
    "owners: [alice]\n"
    "---\n"
    "\n"
    "# Graph query engine\n"
    "\n"
    "## Query surface\n"
    "\n"
    "The shared views live here.\n"
)

REQ_GOOD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST read sizes through "
    "`specs/architecture/graph-query-engine.md`'s \"Query surface\" section.\n"
)

REQ_BAD = (
    "# R-FOO-002\n"
    "\n"
    "**R-FOO-002** — Foo MUST read edges through "
    "`specs/architecture/graph-query-engine.md`'s \"Nonexistent Heading\" section.\n"
)


def acceptance(ac_id, r_id):
    return (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + r_id + "\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When it runs\n"
        "Then it behaves\n"
        "```\n"
    )


def build_fixture(root):
    write(root / "specs" / "glossary.md", "# Glossary\n\n- **Thing** — a thing.\n")
    write(root / "specs" / "architecture" / "graph-query-engine.md", ARCH_MD)
    comp = root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQ_GOOD)
    write(comp / "requirements" / "R-FOO-002.md", REQ_BAD)
    write(comp / "acceptance" / "AC-FOO-001.md", acceptance("AC-FOO-001", "R-FOO-001"))
    write(comp / "acceptance" / "AC-FOO-002.md", acceptance("AC-FOO-002", "R-FOO-002"))
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def test_only_nonexistent_heading_citation_gets_r_cite_002(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = citation_checker.check(repo_root)

    cite_002 = [f for f in findings if field(f, "rule_id") == "R-CITE-002"]
    files = {field(f, "file") for f in cite_002}

    good = "specs/components/foo/requirements/R-FOO-001.md"
    bad = "specs/components/foo/requirements/R-FOO-002.md"

    assert good not in files, cite_002
    assert files == {bad}, cite_002
    assert len(cite_002) == 1, cite_002
    assert field(cite_002[0], "severity") in ("fail", "warn")
    assert isinstance(field(cite_002[0], "line"), int)