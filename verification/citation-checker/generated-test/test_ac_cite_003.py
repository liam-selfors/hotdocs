# hotdocs-criterion: sha256:4afabea7a812311e37279498436751cdb210eeb730895762b596db2ba7b7414e
import citation_checker

from pathlib import Path


RULE = "R-CITE-003"


def _get(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


COMPONENT_MD = """---
id: comp-demo
title: Demo
status: draft
owners: [alice]
sealed: true
source_path: legacy/demo
---

# Demo

## Purpose

A demo fixture component used only by this test.

## Scope

- In scope: fixture behavior.
- Out of scope: everything else.

## Definitions

None.

## Behavior

See the requirements directory.

## Interfaces

See the interface directory.

## Data

None.

## Acceptance criteria

See the acceptance directory.

## Non-functional constraints

None.

## Open questions

## Change log

- Created as a test fixture.
"""


def _build_repo(root, glossary_entries, requirements):
    root = Path(root)
    glossary_lines = ["# Glossary", "", "Canonical vocabulary for the fixture.", ""]
    for term, definition in glossary_entries:
        glossary_lines.append("- **%s** — %s" % (term, definition))
    glossary_lines.append("")
    _write(root, "specs/glossary.md", "\n".join(glossary_lines))
    _write(root, "specs/components/demo/component.md", COMPONENT_MD)
    for req_id, text in requirements:
        _write(root, "specs/components/demo/requirements/%s.md" % req_id, text)
        ac_id = req_id.replace("R-", "AC-", 1)
        _write(
            root,
            "specs/components/demo/acceptance/%s.md" % ac_id,
            "# %s\n\nCovers: %s\nKind: llm-judge\n\nThe demo behaves as stated.\n"
            % (ac_id, req_id),
        )
    return root


def _rel(path_value):
    return str(path_value).replace("\\", "/")


def _cite_findings(findings):
    assert isinstance(findings, list)
    return [f for f in findings if _get(f, "rule_id") == RULE]


def _req_path(req_id):
    return "specs/components/demo/requirements/%s.md" % req_id


def test_only_missing_glossary_entry_is_flagged(tmp_path):
    repo = _build_repo(
        tmp_path,
        [("Widget", "a small part used by the fixture.")],
        [
            (
                "R-DEMO-001",
                "# R-DEMO-001\n\n"
                "**R-DEMO-001** — The demo MUST follow the glossary's \"Widget\" definition.\n",
            ),
            (
                "R-DEMO-002",
                "# R-DEMO-002\n\n"
                "**R-DEMO-002** — The demo MUST follow the glossary's \"Gizmo\" definition.\n",
            ),
        ],
    )

    findings = citation_checker.check(repo)
    cite = _cite_findings(findings)

    assert len(cite) == 1, cite
    finding = cite[0]
    assert _rel(_get(finding, "file")) == _req_path("R-DEMO-002")
    line = _get(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line == 3
    assert _get(finding, "severity") in ("fail", "warn")
    assert isinstance(_get(finding, "message"), str)

    flagged_files = {_rel(_get(f, "file")) for f in cite}
    assert _req_path("R-DEMO-001") not in flagged_files


def test_wrap_trailing_punctuation_case_and_placeholder(tmp_path):
    repo = _build_repo(
        tmp_path,
        [("Widget frame", "the frame that holds a widget.")],
        [
            (
                "R-DEMO-001",
                "# R-DEMO-001\n\n"
                "**R-DEMO-001** — The demo MUST follow the glossary's \"Widget\n"
                "  frame\" definition when building.\n",
            ),
            (
                "R-DEMO-002",
                "# R-DEMO-002\n\n"
                "**R-DEMO-002** — The demo MUST follow the glossary's \"Widget frame,\" and\n"
                "nothing else.\n",
            ),
            (
                "R-DEMO-003",
                "# R-DEMO-003\n\n"
                "**R-DEMO-003** — The demo MUST follow the glossary's \"widget frame\" definition.\n",
            ),
            (
                "R-DEMO-004",
                "# R-DEMO-004\n\n"
                "**R-DEMO-004** — A citation has the form the glossary's \"<Term>\" in prose.\n",
            ),
        ],
    )

    findings = citation_checker.check(repo)
    cite = _cite_findings(findings)

    flagged_files = [_rel(_get(f, "file")) for f in cite]
    assert flagged_files == [_req_path("R-DEMO-003")], cite

    finding = cite[0]
    line = _get(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line == 3
    assert _get(finding, "severity") in ("fail", "warn")

    assert _req_path("R-DEMO-001") not in flagged_files
    assert _req_path("R-DEMO-002") not in flagged_files
    assert _req_path("R-DEMO-004") not in flagged_files