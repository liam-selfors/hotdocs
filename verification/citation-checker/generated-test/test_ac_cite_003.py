import citation_checker

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = """---
id: comp-widgets
title: Widgets
status: ratified
owners: [tester]
sealed: true
source_path: legacy/widgets/
last_ratified_commit: 0000000000000000000000000000000000000000
---

# Widgets

## Purpose

Handles widgets for testing citations.

## Scope

- In scope: widgets.
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path, glossary_entries, requirement_bodies):
    """requirement_bodies: list of (req_id, body_text). Returns rel paths by req id."""
    glossary = "# Glossary\n\nCanonical vocabulary.\n\n"
    for term, definition in glossary_entries:
        glossary += "- **%s** — %s\n" % (term, definition)
    _write(repo_root / "specs" / "glossary.md", glossary)

    comp_dir = repo_root / "specs" / "components" / "widgets"
    _write(comp_dir / "component.md", COMPONENT_MD)
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- None beyond the defaults; measured by inspection.\n",
    )

    rel_paths = {}
    for idx, (req_id, body) in enumerate(requirement_bodies, start=1):
        req_path = comp_dir / "requirements" / ("%s.md" % req_id)
        _write(req_path, body)
        rel_paths[req_id] = req_path.relative_to(repo_root).as_posix()
        ac_id = "AC-WID-%03d" % idx
        _write(
            comp_dir / "acceptance" / ("%s.md" % ac_id),
            "# %s\n\nCovers: %s\nKind: llm-judge\n\nThe requirement holds.\n"
            % (ac_id, req_id),
        )
    return rel_paths


def _cite3_findings(repo_root: Path):
    findings = citation_checker.check(repo_root)
    return [f for f in findings if field(f, "rule_id") == "R-CITE-003"]


def _norm(p) -> str:
    return str(p).replace("\\", "/")


def test_missing_glossary_entry_citation_flagged_only(tmp_path):
    repo_root = tmp_path / "repo"
    rel = _build_fixture(
        repo_root,
        [("Widget", "a thing that is cited by the fixture.")],
        [
            (
                "R-WID-001",
                "# R-WID-001\n\n**R-WID-001** — Every input MUST be handled as\n"
                "described by the glossary's \"Widget\" entry.\n",
            ),
            (
                "R-WID-002",
                "# R-WID-002\n\n**R-WID-002** — Every output MUST be shaped as\n"
                "described by the glossary's \"Gizmo\" entry.\n",
            ),
        ],
    )

    found = _cite3_findings(repo_root)
    files = [_norm(field(f, "file")) for f in found]

    assert len(found) == 1, found
    assert files == [rel["R-WID-002"]], found
    assert rel["R-WID-001"] not in files
    assert isinstance(field(found[0], "line"), int)


def test_wrap_trailing_punct_and_placeholder_ok_but_case_mismatch_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    rel = _build_fixture(
        repo_root,
        [("Widget Frame", "the frame holding a widget.")],
        [
            (
                "R-WID-001",
                "# R-WID-001\n\n**R-WID-001** — Every widget MUST sit in what\n"
                "the glossary's \"Widget\n  Frame\" entry describes.\n",
            ),
            (
                "R-WID-002",
                "# R-WID-002\n\n**R-WID-002** — Every frame MUST follow the\n"
                "glossary's \"Widget Frame,\" which defines its shape.\n",
            ),
            (
                "R-WID-003",
                "# R-WID-003\n\n**R-WID-003** — Every frame MUST be sized per\n"
                "the glossary's \"widget frame\" entry.\n",
            ),
            (
                "R-WID-004",
                "# R-WID-004\n\n**R-WID-004** — Every citation of the form\n"
                "the glossary's \"<Term>\" MUST resolve to a real entry.\n",
            ),
        ],
    )

    found = _cite3_findings(repo_root)
    files = [_norm(field(f, "file")) for f in found]

    assert len(found) == 1, found
    assert files == [rel["R-WID-003"]], found
    for ok in ("R-WID-001", "R-WID-002", "R-WID-004"):
        assert rel[ok] not in files, (ok, found)