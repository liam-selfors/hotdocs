# hotdocs-criterion: sha256:8311a41ecd0daeb231c63b145c4529c2854e063100831b4a89409737c34d66c7
import sys
from pathlib import Path

import pytest

import citation_checker


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str, rationale: str) -> str:
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}\n"
        "---\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"The {slug} component does a small, well-described job.\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"{rationale}\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: its own job.\n"
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
        "- Initial version.\n"
    )


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a small thing used only in this fixture.\n",
    )

    _write(
        root / "specs" / "decisions" / "D100.md",
        "---\n"
        "id: D100\n"
        "title: A real formal decision\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: 0000000000000000000000000000000000000000\n"
        "---\n"
        "\n"
        "# A real formal decision\n"
        "\n"
        "This decision exists as a file.\n",
    )

    _write(
        root / "notes" / "initial-ideas.md",
        "# Initial ideas\n\n## D7\n\nAn informal brainstorm decision, never formalized.\n",
    )

    # First: cites a decision number with no corresponding specs/decisions/ file.
    _write(
        root / "specs" / "components" / "alpha" / "component.md",
        _component_md(
            "alpha",
            "This design was chosen per D9999, which settled the question.",
        ),
    )

    # Second: cites D7, one of the informal D1-D14 never formalized as files.
    _write(
        root / "specs" / "components" / "beta" / "component.md",
        _component_md(
            "beta",
            "This design follows `notes/initial-ideas.md`'s D7, an informal "
            "brainstorm decision from the original notes.",
        ),
    )

    return root


def test_only_unresolved_decision_citation_gets_r_cite_001(repo_root):
    findings = citation_checker.check(repo_root)

    assert isinstance(findings, list)

    cite_001 = [f for f in findings if _get(f, "rule_id") == "R-CITE-001"]

    alpha_rel = "specs/components/alpha/component.md"
    beta_rel = "specs/components/beta/component.md"

    def _norm(p):
        return str(p).replace("\\", "/") if p is not None else None

    alpha_findings = [f for f in cite_001 if _norm(_get(f, "file")) == alpha_rel]
    beta_findings = [f for f in cite_001 if _norm(_get(f, "file")) == beta_rel]

    # The first citation (no corresponding decision file) is flagged.
    assert len(alpha_findings) == 1, findings

    # The second citation (D7, an informal D1-D14 decision) is not flagged.
    assert beta_findings == [], findings

    # Only the first citation gets a R-CITE-001 finding at all.
    assert len(cite_001) == 1, findings

    finding = alpha_findings[0]
    assert _get(finding, "severity") in ("fail", "warn")
    line = _get(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line >= 1
    message = _get(finding, "message")
    assert isinstance(message, str) and message


def test_findings_have_exact_documented_fields(repo_root):
    findings = citation_checker.check(repo_root)
    for f in findings:
        if isinstance(f, dict):
            assert set(f.keys()) == {"rule_id", "severity", "file", "line", "message"}
        assert _get(f, "severity") in ("fail", "warn")
        assert isinstance(_get(f, "line"), int)
        file_value = _get(f, "file")
        assert file_value is not None
        assert not Path(str(file_value)).is_absolute()