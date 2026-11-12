from pathlib import Path

import citation_checker


GOOD_REQ_REL = "specs/components/foo/requirements/R-FOO-001.md"
BAD_REQ_REL = "specs/components/foo/requirements/R-FOO-002.md"
ARCH_REL = "specs/architecture/graph-query-engine.md"


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [alice]
sealed: true
source_path: legacy/foo
---

# Foo

## Purpose

Foo does one small thing so that citation checks can be exercised.

## Scope

- In scope: exercising citation checks.
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

- Initial version.
"""

ARCH_MD = """---
id: arch-graph-query-engine
title: Graph query engine
status: draft
owners: [alice]
---

# Graph query engine

## Purpose

Shared views over the corpus.

## Query surface

The shared views live here.
"""

GOOD_REQ = """# R-FOO-001

**R-FOO-001** — The foo MUST read its facts through
`specs/architecture/graph-query-engine.md`'s "Query surface" section.
"""

BAD_REQ = """# R-FOO-002

**R-FOO-002** — The foo MUST also read its facts through
`specs/architecture/graph-query-engine.md`'s "Nonexistent Heading" section.
"""

GLOSSARY_MD = """# Glossary

- **Widget** — a thing used only by this test fixture.
"""


def _acceptance(ac_id: str, req_id: str) -> str:
    return (
        f"# {ac_id}\n\n"
        f"Covers: {req_id}\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a foo\n"
        "When it runs\n"
        "Then it works\n"
        "```\n"
    )


def _build_repo(root: Path, include_bad: bool) -> None:
    _write(root, "specs/glossary.md", GLOSSARY_MD)
    _write(root, ARCH_REL, ARCH_MD)
    _write(root, "specs/components/foo/component.md", COMPONENT_MD)
    _write(root, GOOD_REQ_REL, GOOD_REQ)
    _write(
        root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        _acceptance("AC-FOO-001", "R-FOO-001"),
    )
    if include_bad:
        _write(root, BAD_REQ_REL, BAD_REQ)
        _write(
            root,
            "specs/components/foo/acceptance/AC-FOO-002.md",
            _acceptance("AC-FOO-002", "R-FOO-002"),
        )


def _cite002_findings(findings):
    return [f for f in findings if _get(f, "rule_id") == "R-CITE-002"]


def _norm(path_value) -> str:
    return str(path_value).replace("\\", "/")


def test_only_missing_heading_citation_gets_r_cite_002_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, include_bad=True)

    findings = citation_checker.check(repo_root)

    assert isinstance(findings, list), findings
    cite = _cite002_findings(findings)
    files = [_norm(_get(f, "file")) for f in cite]

    assert files == [BAD_REQ_REL], (
        f"expected exactly one R-CITE-002 finding on {BAD_REQ_REL}, got {cite!r}"
    )
    assert GOOD_REQ_REL not in files, cite

    finding = cite[0]
    assert _get(finding, "severity") in ("fail", "warn"), finding
    line = _get(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool), finding
    assert line >= 1, finding
    message = _get(finding, "message")
    assert isinstance(message, str) and message, finding


def test_resolving_citation_alone_gets_no_r_cite_002_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, include_bad=False)

    findings = citation_checker.check(repo_root)

    assert isinstance(findings, list), findings
    cite = _cite002_findings(findings)
    assert cite == [], f"expected no R-CITE-002 findings, got {cite!r}"