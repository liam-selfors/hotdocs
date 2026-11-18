# hotdocs-criterion: sha256:e5286c564cdef92e4a1895c5b25ac087612e6d291e3230ff69114d6e2624a28b
"""AC-SIZE-002: R-SIZE-002 fires a distinct warning only when two or more
size-cap dimensions are over their warn threshold for the same component."""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: " + slug + " component\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# " + slug + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component used to exercise size checks.\n"
        + "\n"
        + "## Scope\n"
        + "\n"
        + "- In scope: fixture behavior.\n"
        + "- Out of scope: everything else.\n"
        + "\n"
        + "## Definitions\n"
        + "\n"
        + "None.\n"
        + "\n"
        + "## Behavior\n"
        + "\n"
        + "See `requirements/`.\n"
        + "\n"
        + "## Interfaces\n"
        + "\n"
        + "See `interface/`.\n"
        + "\n"
        + "## Data\n"
        + "\n"
        + "See `interface/data/`.\n"
        + "\n"
        + "## Acceptance criteria\n"
        + "\n"
        + "See `acceptance/`.\n"
        + "\n"
        + "## Non-functional constraints\n"
        + "\n"
        + "See `constraints.md`.\n"
        + "\n"
        + "## Open questions\n"
        + "\n"
        + "## Change log\n"
        + "\n"
        + "- Initial fixture.\n"
    )


def _build_component(repo_root, slug, upper, loc, constraint_words):
    comp_dir = repo_root / "specs" / "components" / slug
    _write(comp_dir / "component.md", _component_md(slug))
    _write(
        comp_dir / "requirements" / ("R-" + upper + "-001.md"),
        "**R-" + upper + "-001** — The component MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        + "Covers: R-" + upper + "-001\n"
        + "Kind: compiled\n\n"
        + "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    body = "# Constraints\n\n- Fast enough.\n"
    if constraint_words:
        words = []
        for i in range(constraint_words):
            words.append("lorem")
            if i % 20 == 19:
                words.append("\n")
        body += "\n" + " ".join(words) + "\n"
    _write(comp_dir / "constraints.md", body)

    module_name = slug.replace("-", "_")
    code_lines = []
    for i in range(loc):
        code_lines.append("value_" + str(i) + " = " + repr(i))
    _write(
        repo_root / "gen" / slug / (module_name + ".py"),
        "\n".join(code_lines) + "\n",
    )


def _mentions(finding, slug):
    text = str(field(finding, "file")) + " " + str(field(finding, "message"))
    return slug in text


def test_r_size_002_fires_only_for_two_dimensions_over_warn(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Both generated_code_loc (1000 > 800) and component_doc_words (~2800 > 2000)
    # over warn, both below their hard-fail thresholds.
    _build_component(repo_root, "alphacomp", "ALPHACOMP", 1000, 2800)
    # Only generated_code_loc over warn.
    _build_component(repo_root, "betacomp", "BETACOMP", 1000, 0)

    findings = size_checker.check(repo_root)

    size2 = [f for f in findings if field(f, "rule_id") == "R-SIZE-002"]

    # R-SIZE-002 never hard-fails.
    for f in size2:
        assert field(f, "severity") == "warn"

    alpha = [f for f in size2 if _mentions(f, "alphacomp")]
    beta = [f for f in size2 if _mentions(f, "betacomp")]

    assert len(alpha) >= 1, findings
    assert beta == [], beta

    msg = str(field(alpha[0], "message"))
    low = msg.lower()
    assert ("generated_code_loc" in low) or ("generated code" in low), msg
    assert ("component_doc_words" in low) or ("component doc" in low) or (
        "doc words" in low
    ), msg
    assert "1000" in msg, msg
    assert "SPEC_GUIDELINES.md" in msg, msg
    assert ("§4" in msg) or ("section 4" in low) or ("§ 4" in msg), msg

    assert isinstance(field(alpha[0], "line"), int)
    assert not Path(str(field(alpha[0], "file"))).is_absolute()

    # Sanity: the second component's single over-warn dimension was seen
    # (as an ordinary R-SIZE-001 finding), so its absence above is meaningful.
    beta_size1 = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-001" and _mentions(f, "betacomp")
    ]
    assert len(beta_size1) >= 1, findings