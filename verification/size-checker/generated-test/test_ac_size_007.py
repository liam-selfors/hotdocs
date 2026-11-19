# hotdocs-criterion: sha256:3ad487cc9e03cd8fe11f31166f5a260e20575e73a2f90ce387e102f53e7ae5e2
import re
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small thing.\n"
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
    "- Initial.\n"
)

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST do the small thing.\n"
)


def acceptance_text(total_words):
    header = "Covers: R-FOO-001\nKind: compiled\n\n"
    header_words = len(header.split())
    filler = " ".join(["word"] * (total_words - header_words))
    text = header + filler + "\n"
    assert len(text.split()) == total_words
    return text


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(acceptance_text(300))
    (comp / "acceptance" / "AC-FOO-002.md").write_text(acceptance_text(520))
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n")
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Thing** — a thing.\n"
    )


def norm(path):
    return str(path).replace("\\", "/")


def test_ac_size_007_per_file_word_count_warn_and_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    first = "specs/components/foo/acceptance/AC-FOO-001.md"
    second = "specs/components/foo/acceptance/AC-FOO-002.md"

    findings = size_checker.check(repo_root)
    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    first_findings = [f for f in size3 if norm(field(f, "file")) == first]
    second_findings = [f for f in size3 if norm(field(f, "file")) == second]

    assert len(first_findings) == 1, size3
    assert len(second_findings) == 1, size3

    f1 = first_findings[0]
    f2 = second_findings[0]

    assert field(f1, "severity") == "warn"
    assert field(f2, "severity") == "fail"

    assert re.search(r"\b300\b", field(f1, "message")), field(f1, "message")
    assert re.search(r"\b520\b", field(f2, "message")), field(f2, "message")

    assert isinstance(field(f1, "line"), int)
    assert isinstance(field(f2, "line"), int)

    # No R-SIZE-003 finding for any other file (e.g. the short requirement).
    others = [
        f for f in size3 if norm(field(f, "file")) not in (first, second)
    ]
    assert others == []