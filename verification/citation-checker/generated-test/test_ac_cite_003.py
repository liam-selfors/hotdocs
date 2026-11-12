"""Generated test for AC-CITE-003 (covers R-CITE-003).

Exercises citation_checker.check(repo_root) against small synthetic spec
corpora, using the real corpus-loader resolved through the tool root (no
dependency is faked here).
"""
from pathlib import Path

import citation_checker


COMPONENT = "fixture"
REQ_DIR = f"specs/components/{COMPONENT}/requirements"

EXPECTED_KEYS = {"rule_id", "severity", "file", "line", "message"}


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_root_md() -> str:
    return (
        "---\n"
        "id: comp-fixture\n"
        "title: Fixture component\n"
        "status: draft\n"
        "owners: [fixture-owner]\n"
        "sealed: true\n"
        "source_path: legacy/fixture\n"
        "---\n"
        "\n"
        "# Fixture component\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture used only to exercise citation checking.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: fixture behavior.\n"
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
        "- Created as a test fixture.\n"
    )


def _acceptance_md(n: int) -> str:
    return (
        f"# AC-FIX-00{n}\n"
        "\n"
        f"Covers: R-FIX-00{n}\n"
        "Kind: generated-test\n"
        "\n"
        "The fixture behaves as its requirement states.\n"
    )


def _build_repo(root: Path, glossary_entries, requirement_bodies) -> None:
    """requirement_bodies: list of body strings, one per requirement."""
    glossary = "# Glossary\n\nCanonical vocabulary for the fixture.\n\n"
    for term, definition in glossary_entries:
        glossary += f"- **{term}** — {definition}\n"
    _write(root, "specs/glossary.md", glossary)
    _write(root, f"specs/components/{COMPONENT}/component.md", _component_root_md())
    _write(
        root,
        f"specs/components/{COMPONENT}/constraints.md",
        "# Constraints\n\nNone beyond the defaults.\n",
    )
    for i, body in enumerate(requirement_bodies, start=1):
        _write(root, f"{REQ_DIR}/R-FIX-00{i}.md", body)
        _write(
            root,
            f"specs/components/{COMPONENT}/acceptance/AC-FIX-00{i}.md",
            _acceptance_md(i),
        )


def _cite_findings(findings):
    assert isinstance(findings, list)
    for f in findings:
        if isinstance(f, dict):
            assert set(f.keys()) == EXPECTED_KEYS
    return [f for f in findings if _get(f, "rule_id") == "R-CITE-003"]


def _assert_finding_shape(f):
    assert _get(f, "severity") in ("fail", "warn")
    line = _get(f, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line >= 1
    message = _get(f, "message")
    assert isinstance(message, str) and message.strip()


def test_missing_glossary_entry_is_flagged_existing_one_is_not(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_repo(
        root,
        [("Widget", "a small reusable thing used by the fixture.")],
        [
            "# R-FIX-001\n"
            "\n"
            "**R-FIX-001** — The fixture MUST use the glossary's \"Widget\" as defined.\n",
            "# R-FIX-002\n"
            "\n"
            "**R-FIX-002** — The fixture MUST use the glossary's \"Gizmo\" as defined.\n",
        ],
    )

    findings = citation_checker.check(root)
    cite = _cite_findings(findings)

    assert len(cite) == 1, cite
    f = cite[0]
    assert _get(f, "file") == f"{REQ_DIR}/R-FIX-002.md"
    _assert_finding_shape(f)
    assert _get(f, "line") == 3
    assert "Gizmo" in _get(f, "message")


def test_wrapped_punctuated_and_placeholder_pass_only_case_mismatch_flagged(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_repo(
        root,
        [("Big Widget", "a larger reusable thing used by the fixture.")],
        [
            # 1: citation hard-wrapped across two lines -> resolves
            "# R-FIX-001\n"
            "\n"
            "**R-FIX-001** — The fixture MUST use the glossary's \"Big\n"
            "  Widget\" as defined.\n",
            # 2: trailing comma inside the closing quote -> resolves
            "# R-FIX-002\n"
            "\n"
            "**R-FIX-002** — The fixture MUST use the glossary's \"Big Widget,\" as defined.\n",
            # 3: different letter case -> MUST be flagged
            "# R-FIX-003\n"
            "\n"
            "**R-FIX-003** — The fixture MUST use the glossary's \"big widget\" as defined.\n",
            # 4: placeholder, not a citation
            "# R-FIX-004\n"
            "\n"
            "**R-FIX-004** — A citation takes the form the glossary's \"<Term>\" in prose.\n",
        ],
    )

    findings = citation_checker.check(root)
    cite = _cite_findings(findings)

    files = [_get(f, "file") for f in cite]
    assert files == [f"{REQ_DIR}/R-FIX-003.md"], cite
    f = cite[0]
    _assert_finding_shape(f)
    assert _get(f, "line") == 3