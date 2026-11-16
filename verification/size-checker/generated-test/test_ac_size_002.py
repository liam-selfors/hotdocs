"""AC-SIZE-002 (Covers: R-SIZE-002).

Given a component whose generated_code_loc and component_doc_words are both
over their warn thresholds, and a second component with only
generated_code_loc over its warn threshold,
When check(repo_root) runs,
Then the first component gets a distinct R-SIZE-002 warning naming both
dimensions and SPEC_GUIDELINES.md Section 4, and the second component gets
no R-SIZE-002 finding at all.
"""

from pathlib import Path

import size_checker


GEN_LOC = 1000  # warn above 800, hard fail above 1500


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _filler(n_words: int, token: str) -> str:
    words = [f"{token}{i % 7}" for i in range(n_words)]
    lines = [" ".join(words[i:i + 20]) for i in range(0, len(words), 20)]
    return "\n".join(lines)


def _component_md(slug: str, scope_words: int) -> str:
    scope_text = "- In scope: the synthetic {slug} fixture behavior.\n".format(slug=slug)
    if scope_words:
        scope_text += "\n" + _filler(scope_words, "scope") + "\n"
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()}\n"
        "status: draft\n"
        "owners: [team-test]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        f"# {slug.capitalize()}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"A small synthetic component named {slug} used as a test fixture.\n"
        "\n"
        "## Scope\n"
        "\n"
        f"{scope_text}"
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
        "- Initial fixture.\n"
    )


def _gen_code(loc: int) -> str:
    lines = ["# synthetic generated module", ""]
    for i in range(loc):
        lines.append(f"value_{i} = {i}")
        if i % 100 == 0:
            lines.append("")
            lines.append("    # an indented comment line")
    return "\n".join(lines) + "\n"


def _make_component(repo: Path, slug: str, scope_words: int,
                    constraint_words: int, loc: int) -> None:
    upper = slug.upper()
    comp = repo / "specs" / "components" / slug
    _write(comp / "component.md", _component_md(slug, scope_words))
    _write(
        comp / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The component MUST exist "
        "as a fixture.\n",
    )
    _write(
        comp / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: compiled\n\n"
        "```gherkin\nGiven the fixture\nWhen it is loaded\n"
        "Then it exists\n```\n",
    )
    constraints = "# Constraints\n\n- None measurable beyond existence.\n"
    if constraint_words:
        constraints += "\n" + _filler(constraint_words, "constraint") + "\n"
    _write(comp / "constraints.md", constraints)
    _write(repo / "gen" / slug / f"{slug}.py", _gen_code(loc))


def _build_repo(repo: Path) -> None:
    _write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test component.\n",
    )
    # alpha: generated_code_loc (1000 > 800) AND component_doc_words
    # (~3000 > 2000, < 4000) both over warn.
    _make_component(repo, "alpha", scope_words=2400, constraint_words=600,
                    loc=GEN_LOC)
    # beta: only generated_code_loc over warn; docs tiny.
    _make_component(repo, "beta", scope_words=0, constraint_words=0,
                    loc=GEN_LOC)


def _mentions_loc(msg: str) -> bool:
    low = msg.lower()
    return "generated_code_loc" in low or "generated code" in low


def _mentions_doc_words(msg: str) -> bool:
    low = msg.lower()
    return "component_doc_words" in low or "component doc" in low


def _mentions_section4(msg: str) -> bool:
    low = msg.lower()
    return "§4" in msg or "section 4" in low or "sec. 4" in low


def test_ac_size_002_multi_dimension_warn_signal(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _build_repo(repo)

    findings = size_checker.check(repo)
    assert isinstance(findings, list)

    # Sanity: beta's generated_code_loc really is over its warn threshold
    # (so its lack of an R-SIZE-002 finding is meaningful).
    beta_r1 = [
        f for f in findings
        if field(f, "rule_id") == "R-SIZE-001" and "beta" in field(f, "file")
    ]
    assert beta_r1, f"expected an R-SIZE-001 finding for beta, got {findings!r}"

    r2 = [f for f in findings if field(f, "rule_id") == "R-SIZE-002"]

    alpha_r2 = [f for f in r2 if "alpha" in field(f, "file")]
    beta_r2 = [
        f for f in r2
        if "beta" in field(f, "file") or "beta" in field(f, "message")
    ]

    # Second component: no R-SIZE-002 finding at all.
    assert beta_r2 == [], f"beta must get no R-SIZE-002 finding: {beta_r2!r}"

    # First component: exactly one distinct R-SIZE-002 warning.
    assert len(alpha_r2) == 1, f"expected one R-SIZE-002 for alpha: {r2!r}"
    assert len(r2) == 1, f"only alpha should get R-SIZE-002: {r2!r}"

    finding = alpha_r2[0]
    assert field(finding, "severity") == "warn"
    assert isinstance(field(finding, "line"), int)
    file_rel = field(finding, "file")
    assert not Path(file_rel).is_absolute()
    assert "alpha" in file_rel

    message = field(finding, "message")
    assert _mentions_loc(message), message
    assert _mentions_doc_words(message), message
    assert "SPEC_GUIDELINES.md" in message, message
    assert _mentions_section4(message), message
    # Current value of the deterministic dimension is named.
    assert str(GEN_LOC) in message, message

    # R-SIZE-002 never hard-fails.
    assert all(field(f, "severity") != "fail" for f in r2)