# hotdocs-criterion: sha256:a9fb2574f0dc7e03ba98e9e2986d372aec08b1c6d4f2bd026b3e1933fba4a9b8
"""AC-CITE-005: builds_on entries must resolve to specs/decisions/D<N>.md,
except D1-D14, which were never formalized as files.

Given a decision record's builds_on naming a decision number with no
  corresponding specs/decisions/ file, and a second record's builds_on
  naming D7, one of D1-D14, never formalized as files
When check(repo_root) runs
Then only the first gets an R-CITE-005 finding
"""

from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(doc_id, title, builds_on):
    lines = [
        "---",
        "id: " + doc_id,
        "title: " + title,
        "status: draft",
        "owners: [team-a]",
    ]
    if builds_on is not None:
        lines.append("builds_on: [" + ", ".join(builds_on) + "]")
    lines.append("---")
    lines.append("")
    lines.append("# " + title)
    lines.append("")
    lines.append("A decision record used as a test fixture.")
    lines.append("")
    return "\n".join(lines)


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )
    decisions = specs / "decisions"
    # First record: builds_on names a decision number with no file.
    _write(
        decisions / "D100.md",
        _decision("D100", "Dangling builds_on", ["D500"]),
    )
    # Second record: builds_on names D7, one of the never-formalized D1-D14.
    _write(
        decisions / "D101.md",
        _decision("D101", "Informal builds_on", ["D7"]),
    )


def _cite005(findings):
    return [f for f in findings if field(f, "rule_id") == "R-CITE-005"]


def test_only_unresolved_builds_on_gets_r_cite_005(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = citation_checker.check(repo_root)

    assert isinstance(findings, list)
    hits = _cite005(findings)
    files = [field(f, "file") for f in hits]

    assert len(hits) == 1, "expected exactly one R-CITE-005 finding, got: " + repr(hits)
    assert files == ["specs/decisions/D100.md"], repr(files)
    assert "specs/decisions/D101.md" not in files

    only = hits[0]
    assert field(only, "severity") in ("fail", "warn")
    assert isinstance(field(only, "line"), int)
    assert isinstance(field(only, "message"), str)


def test_d7_alone_produces_no_r_cite_005(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )
    _write(
        specs / "decisions" / "D101.md",
        _decision("D101", "Informal builds_on", ["D7"]),
    )

    findings = citation_checker.check(repo_root)

    assert _cite005(findings) == []


def test_missing_number_alone_produces_r_cite_005(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )
    _write(
        specs / "decisions" / "D100.md",
        _decision("D100", "Dangling builds_on", ["D500"]),
    )

    findings = citation_checker.check(repo_root)

    hits = _cite005(findings)
    assert [field(f, "file") for f in hits] == ["specs/decisions/D100.md"]