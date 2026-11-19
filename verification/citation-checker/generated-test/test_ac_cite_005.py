# hotdocs-criterion: sha256:a9fb2574f0dc7e03ba98e9e2986d372aec08b1c6d4f2bd026b3e1933fba4a9b8
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(doc_id, builds_on):
    return (
        "---\n"
        + "id: " + doc_id + "\n"
        + "title: Decision " + doc_id + "\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "builds_on: [" + ", ".join(builds_on) + "]\n"
        + "---\n"
        + "\n"
        + "# " + doc_id + "\n"
        + "\n"
        + "A decision record used as a test fixture.\n"
    )


def test_ac_cite_005_only_unresolved_non_historical_builds_on_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )

    # First record: builds_on names D99, which has no specs/decisions/ file.
    _write(specs / "decisions" / "D100.md", _decision("D100", ["D99"]))
    # Second record: builds_on names D7, one of D1-D14, never formalized as files.
    _write(specs / "decisions" / "D101.md", _decision("D101", ["D7"]))

    assert not (specs / "decisions" / "D99.md").exists()
    assert not (specs / "decisions" / "D7.md").exists()

    findings = citation_checker.check(repo_root)

    cite005 = [f for f in findings if field(f, "rule_id") == "R-CITE-005"]
    files = [field(f, "file") for f in cite005]

    assert len(cite005) == 1, findings
    assert files == ["specs/decisions/D100.md"], findings
    assert "specs/decisions/D101.md" not in files

    only = cite005[0]
    assert field(only, "severity") in ("fail", "warn")
    assert isinstance(field(only, "line"), int)
    assert isinstance(field(only, "message"), str)