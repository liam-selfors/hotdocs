"""AC-SIZE-003 (Covers: R-SIZE-003).

Given one requirement file over 500 words and a second requirement file in
the same component under 250 words, with the component's overall
component_doc_words still under 4000, when check(repo_root) runs, then the
first file gets a fail-severity R-SIZE-003 finding naming its own word
count, the second file gets no R-SIZE-003 finding, and R-SIZE-001's
component_doc_words check does not fire.
"""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [tester]
sealed: true
source_path: legacy/foo/
---

# Foo

## Purpose

Foo is a small synthetic component used only to exercise per-file size checks.

## Scope

- In scope: nothing beyond this fixture.
- Out of scope: everything else.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial fixture.
"""

CONSTRAINTS_MD = """# Constraints

- None for this fixture.
"""

GLOSSARY_MD = """# Glossary

- **Fixture term** — a term used only by this synthetic fixture.
"""


def _long_requirement_text():
    header = "# R-FOO-001\n\n**R-FOO-001** — The component MUST do the long thing."
    filler_lines = []
    words = []
    for i in range(600):
        words.append("filler")
        if len(words) == 12:
            filler_lines.append(" ".join(words))
            words = []
    if words:
        filler_lines.append(" ".join(words))
    return header + "\n\n" + "\n".join(filler_lines) + "\n"


SHORT_REQUIREMENT = """# R-FOO-002

**R-FOO-002** — The component MUST do the short thing, briefly.
"""

AC_001 = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given a thing
When it runs
Then the long thing happens
```
"""

AC_002 = """# AC-FOO-002

Covers: R-FOO-002
Kind: generated-test

```gherkin
Given a thing
When it runs
Then the short thing happens
```
"""


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path):
    comp = repo_root / "specs" / "components" / "foo"
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    long_text = _long_requirement_text()
    _write(comp / "requirements" / "R-FOO-001.md", long_text)
    _write(comp / "requirements" / "R-FOO-002.md", SHORT_REQUIREMENT)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_001)
    _write(comp / "acceptance" / "AC-FOO-002.md", AC_002)
    return long_text


def test_ac_size_003_per_file_word_count(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    long_text = _build_fixture(repo_root)

    long_count = len(long_text.split())
    short_count = len(SHORT_REQUIREMENT.split())
    assert long_count > 500
    assert short_count < 250

    # Sanity: the component's whole-docs total stays well under 4000 (and 2000).
    comp_dir = repo_root / "specs" / "components" / "foo"
    total = 0
    for p in comp_dir.rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        if text.startswith("---"):
            lines = text.splitlines()
            for idx in range(1, len(lines)):
                if lines[idx].strip() == "---":
                    text = "\n".join(lines[idx + 1:])
                    break
        total += len(text.split())
    assert total < 2000

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    long_rel = "specs/components/foo/requirements/R-FOO-001.md"
    short_rel = "specs/components/foo/requirements/R-FOO-002.md"

    def norm(f):
        return str(field(f, "file")).replace("\\", "/")

    size3 = [f for f in findings if field(f, "rule_id") == "R-SIZE-003"]

    long_findings = [f for f in size3 if norm(f) == long_rel]
    assert long_findings, f"expected an R-SIZE-003 finding for {long_rel}, got {findings!r}"
    fail_findings = [f for f in long_findings if field(f, "severity") == "fail"]
    assert fail_findings, f"expected fail severity, got {long_findings!r}"
    assert any(str(long_count) in str(field(f, "message")) for f in fail_findings), (
        f"expected message naming word count {long_count}, got {fail_findings!r}"
    )
    for f in fail_findings:
        assert isinstance(field(f, "line"), int)

    short_findings = [f for f in size3 if norm(f) == short_rel]
    assert short_findings == [], f"unexpected R-SIZE-003 finding for short file: {short_findings!r}"

    size1 = [f for f in findings if field(f, "rule_id") == "R-SIZE-001"]
    assert size1 == [], f"R-SIZE-001 must not fire: {size1!r}"