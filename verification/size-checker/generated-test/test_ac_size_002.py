# hotdocs-criterion: sha256:e5286c564cdef92e4a1895c5b25ac087612e6d291e3230ff69114d6e2624a28b
"""AC-SIZE-002: a distinct R-SIZE-002 warning fires only when two or more
size-cap dimensions are over their warn threshold for the same component."""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, title):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [team-" + slug + "]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used for size checking.\n"
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
        "- Initial draft.\n"
    )


def _build_component(repo_root, slug, title, constraint_words, code_lines):
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    _write(comp_dir / "component.md", _component_md(slug, title))
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        comp_dir / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — The component MUST do its one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\n"
        "Covers: " + req_id + "\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        "Given a fixture\n"
        "When it runs\n"
        "Then it does its one thing\n"
        "```\n",
    )
    body_words = " ".join(["lorem"] * constraint_words)
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n" + body_words + "\n",
    )
    module_name = slug.replace("-", "_")
    code = "".join("x" + str(i) + " = " + str(i) + "\n" for i in range(code_lines))
    _write(repo_root / "gen" / slug / (module_name + ".py"), code)


def _build_fixture(repo_root):
    for sub in ("product", "architecture", "vars", "decisions"):
        (repo_root / "specs" / sub).mkdir(parents=True, exist_ok=True)
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a test-only thing.\n",
    )
    # alpha: generated_code_loc (900 > 800) AND component_doc_words (> 2000)
    _build_component(repo_root, "alpha", "Alpha", constraint_words=2600, code_lines=900)
    # beta: only generated_code_loc (900 > 800), docs small
    _build_component(repo_root, "beta", "Beta", constraint_words=20, code_lines=900)


def _belongs_to(finding, slug):
    file_value = str(field(finding, "file")).replace("\\", "/")
    message = str(field(finding, "message"))
    return ("components/" + slug + "/") in file_value or slug in message


def _mentions_section_4(message):
    lowered = message.lower()
    return (
        "§4" in lowered
        or "§ 4" in lowered
        or "section 4" in lowered
    )


def test_ac_size_002_distinct_warning_only_for_multi_dimension_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    size2 = [f for f in findings if field(f, "rule_id") == "R-SIZE-002"]

    alpha_findings = [f for f in size2 if _belongs_to(f, "alpha")]
    beta_findings = [f for f in size2 if _belongs_to(f, "beta")]

    # First component gets a distinct R-SIZE-002 warning.
    assert len(alpha_findings) >= 1, size2
    for f in alpha_findings:
        # MUST NOT ever hard-fail.
        assert field(f, "severity") == "warn", f
        assert isinstance(field(f, "line"), int)

    matching = []
    for f in alpha_findings:
        message = str(field(f, "message"))
        normalized = message.lower().replace("_", " ")
        names_code = "generated code" in normalized
        names_docs = "component doc" in normalized
        names_guide = "SPEC_GUIDELINES.md" in message
        if names_code and names_docs and names_guide and _mentions_section_4(message):
            matching.append(f)
    assert matching, [str(field(f, "message")) for f in alpha_findings]

    # Second component (only one dimension over warn) gets no R-SIZE-002 at all.
    assert beta_findings == [], beta_findings

    # Every R-SIZE-002 finding belongs to the first component only.
    for f in size2:
        assert _belongs_to(f, "alpha") and not _belongs_to(f, "beta"), f

    # And R-SIZE-002 never produces a hard failure anywhere.
    assert all(field(f, "severity") != "fail" for f in size2)