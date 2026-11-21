# hotdocs-criterion: sha256:8108e8ea1bbd12a97f8a03dc5c415ced933175af7a4acd5c0100df37a0509428
import re
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
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Does a small thing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the small thing.\n"
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

CLI_MD = (
    "# CLI\n"
    "\n"
    "```\n"
    "foo run --fast\n"
    "foo build \\\n"
    "  --target x\n"
    "\n"
    "foo clean\n"
    "```\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "alpha(x: int) -> int\n"
    "beta(y: str) -> str\n"
    "gamma() -> None\n"
    "delta(a: int, b: int) -> list\n"
    "epsilon(path: Path) -> dict\n"
    "These functions do small things.\n"
    "```\n"
)


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n\n- **Foo** — a thing.\n")
    comp = specs / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the small thing.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it works\n```\n",
    )
    write(comp / "interface" / "cli.md", CLI_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    for name in ("Alpha", "Beta", "Gamma"):
        write(
            comp / "interface" / "data" / (name + ".md"),
            "# " + name + "\n\nA small type.\n",
        )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def test_ac_size_005_interface_surface_eleven_warns(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    findings = size_checker.check(repo_root)

    size_findings = [
        f for f in findings if field(f, "rule_id") == "R-SIZE-001"
    ]
    assert len(size_findings) == 1, size_findings
    finding = size_findings[0]
    assert field(finding, "severity") == "warn"
    message = field(finding, "message")
    assert "interface_surface" in message
    assert re.search(r"(?<!\d)11(?!\d)", message), message
    assert "specs/components/foo/" in field(finding, "file").replace("\\", "/")