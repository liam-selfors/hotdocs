# hotdocs-criterion: sha256:9db2e2ba74b36c5e992e913f58fd7d30616d08131ece05a72a650dff509c0f2b
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def decision_text(doc_id, title, builds_on):
    return (
        "---\n"
        + "id: " + doc_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "builds_on: [" + ", ".join(builds_on) + "]\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "A decision record used as a test fixture.\n"
    )


def test_ac_cite_005_only_unresolved_builds_on_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    specs = repo_root / "specs"

    write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture term** \u2014 a term used only by this fixture.\n",
    )

    # First record: builds_on names a decision number with no file.
    write(
        specs / "decisions" / "D200.md",
        decision_text("D200", "Builds on a missing decision", ["D9999"]),
    )
    # Second record: builds_on names D7, one of D1-D14, never formalized.
    write(
        specs / "decisions" / "D201.md",
        decision_text("D201", "Builds on an informal decision", ["D7"]),
    )

    findings = citation_checker.check(repo_root)

    cite5 = [f for f in findings if field(f, "rule_id") == "R-CITE-005"]
    files = [field(f, "file") for f in cite5]

    assert len(cite5) == 1, cite5
    assert files[0].replace("\\", "/") == "specs/decisions/D200.md"
    assert not any(
        f.replace("\\", "/") == "specs/decisions/D201.md" for f in files
    )

    finding = cite5[0]
    assert field(finding, "severity") in ("fail", "warn")
    assert isinstance(field(finding, "line"), int)
    assert isinstance(field(finding, "message"), str)