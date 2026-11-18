# hotdocs-criterion: sha256:c0f32df6bb1b03862a20bd3ebdcc5b6ec3588e67f48caad6da64e523b4fb590b
import sys
from pathlib import Path

import size_checker


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _norm(path_value):
    return str(path_value).replace("\\", "/") if path_value is not None else None


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path):
    comp_dir = repo_root / "specs" / "components" / "widget"

    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a small synthetic test fixture term.\n",
    )

    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/widget\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Matches existing behavior; do not regenerate.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the widget.\n"
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
        "- Initial.\n",
    )

    filler_words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]
    filler = " ".join(filler_words[i % len(filler_words)] for i in range(600))
    long_text = (
        "# R-WIDGET-001\n\n"
        "**R-WIDGET-001** — The widget MUST behave as described: "
        + filler
        + "\n"
    )
    long_path = comp_dir / "requirements" / "R-WIDGET-001.md"
    _write(long_path, long_text)

    short_text = (
        "# R-WIDGET-002\n\n"
        "**R-WIDGET-002** — The widget MUST remain small and simple.\n"
    )
    short_path = comp_dir / "requirements" / "R-WIDGET-002.md"
    _write(short_path, short_text)

    for n in ("001", "002"):
        _write(
            comp_dir / "acceptance" / f"AC-WIDGET-{n}.md",
            f"# AC-WIDGET-{n}\n\n"
            f"Covers: R-WIDGET-{n}\n"
            "Kind: compiled\n\n"
            "```gherkin\n"
            "Given a widget\n"
            "When it runs\n"
            "Then it works\n"
            "```\n",
        )

    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- None beyond existing behavior.\n",
    )

    long_count = len(long_text.split())
    short_count = len(short_text.split())

    total_words = 0
    for p in comp_dir.rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        total_words += len(text.split())

    return long_path, long_count, short_path, short_count, total_words


def test_ac_size_003_per_file_word_count_isolated_from_aggregate(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    long_path, long_count, short_path, short_count, total_words = _build_fixture(
        repo_root
    )

    # Fixture preconditions per the criterion.
    assert long_count > 500
    assert short_count < 250
    assert total_words < 4000

    long_rel = long_path.relative_to(repo_root).as_posix()
    short_rel = short_path.relative_to(repo_root).as_posix()

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    size3 = [f for f in findings if _field(f, "rule_id") == "R-SIZE-003"]

    long_findings = [f for f in size3 if _norm(_field(f, "file")) == long_rel]
    assert long_findings, (
        f"expected an R-SIZE-003 finding for {long_rel}, got findings: {findings!r}"
    )
    matching = [
        f
        for f in long_findings
        if _field(f, "severity") == "fail"
        and str(long_count) in str(_field(f, "message") or "")
    ]
    assert matching, (
        f"expected a fail-severity R-SIZE-003 finding for {long_rel} naming its "
        f"word count {long_count}, got: {long_findings!r}"
    )
    for f in matching:
        assert isinstance(_field(f, "line"), int)

    short_findings = [f for f in size3 if _norm(_field(f, "file")) == short_rel]
    assert short_findings == [], (
        f"expected no R-SIZE-003 finding for {short_rel}, got: {short_findings!r}"
    )

    size1 = [f for f in findings if _field(f, "rule_id") == "R-SIZE-001"]
    assert size1 == [], (
        f"expected R-SIZE-001's component_doc_words check not to fire, got: {size1!r}"
    )