import re
from pathlib import Path

import size_checker


DUAL = "dualheavy"
CODE_ONLY = "loconly"
LOC_LINES = 1000  # over the 800 warn threshold, under the 1500 hard-fail threshold
BULK_WORDS = 2300  # over the 2000 warn threshold, comfortably under 4000


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str, title: str) -> str:
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [alice]\n"
        "realizes: [P-SIZEFIX]\n"
        "---\n"
        "\n"
        f"# {title}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small synthetic component used only as a size fixture.\n"
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
        "- Created as a fixture.\n"
    )


def _build_component(repo_root: Path, slug: str, prefix: str, bulk_words: int) -> None:
    comp_dir = repo_root / "specs" / "components" / slug
    _write(comp_dir / "component.md", _component_md(slug, slug.capitalize()))
    _write(
        comp_dir / "requirements" / f"R-{prefix}-001.md",
        f"# R-{prefix}-001\n\nThe component MUST return its input unchanged.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{prefix}-001.md",
        f"# AC-{prefix}-001\n\n"
        f"Covers: R-{prefix}-001\n"
        "Kind: generated-test\n\n"
        "Given an integer\nWhen run is called\nThen the same integer is returned\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nrun(x: int) -> int\n```\n\nReturns its input.\n",
    )
    if bulk_words > 0:
        vocab = ["system", "remains", "measurable", "under", "steady", "load", "always"]
        words = [vocab[i % len(vocab)] for i in range(bulk_words)]
        lines = []
        for i in range(0, len(words), 20):
            lines.append(" ".join(words[i:i + 20]))
        body = "\n".join(lines)
    else:
        body = "The component responds promptly."
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n## Performance\n\n" + body + "\n",
    )
    code = "".join(f"v_{i} = {i}\n" for i in range(LOC_LINES))
    _write(repo_root / "gen" / slug / f"{slug}.py", code)


def _build_repo(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "product" / "sizefix.md",
        "---\n"
        "id: P-SIZEFIX\n"
        "title: Size Fixture Capability\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# Size Fixture Capability\n"
        "\n"
        "## Purpose\n\nFixture capability.\n\n"
        "## Scope\n\n- Fixture only.\n\n"
        "### CS-SIZEFIX-001\n\nCovers: P-SIZEFIX\nKind: llm-judge\n\n"
        "Given the fixture\nWhen it runs\nThen nothing happens\n",
    )
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test corpus.\n",
    )
    _build_component(repo_root, DUAL, "DUALHEAVY", BULK_WORDS)
    _build_component(repo_root, CODE_ONLY, "LOCONLY", 0)


def _belongs(finding, slug: str) -> bool:
    file_val = str(_get(finding, "file") or "").replace("\\", "/")
    message = str(_get(finding, "message") or "")
    if f"specs/components/{slug}/" in file_val or f"gen/{slug}/" in file_val:
        return True
    if file_val.rstrip("/").endswith(f"/{slug}") or file_val == slug:
        return True
    return re.search(rf"(?<![\w-]){re.escape(slug)}(?![\w])", message) is not None or (
        f"comp-{slug}" in message
    )


def test_multi_dimension_warn_signal_only_for_component_with_two_dimensions(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    findings = size_checker.check(repo_root)
    findings = list(findings)

    for f in findings:
        for key in ("rule_id", "severity", "file", "line", "message"):
            assert _get(f, key) is not None, f"finding missing {key}: {f!r}"

    size002 = [f for f in findings if _get(f, "rule_id") == "R-SIZE-002"]

    # R-SIZE-002 MUST NOT ever hard-fail.
    for f in size002:
        assert _get(f, "severity") == "warn", f"R-SIZE-002 finding hard-failed: {f!r}"

    # Fixture sanity: the code-only component really is over its LOC warn threshold.
    code_only_findings = [f for f in findings if _belongs(f, CODE_ONLY)]
    assert any(
        _get(f, "rule_id") == "R-SIZE-001" for f in code_only_findings
    ), f"expected an R-SIZE-001 finding for {CODE_ONLY}; got {findings!r}"

    # Second component: no R-SIZE-002 finding at all.
    code_only_002 = [f for f in size002 if _belongs(f, CODE_ONLY)]
    assert code_only_002 == [], f"unexpected R-SIZE-002 for {CODE_ONLY}: {code_only_002!r}"

    # First component: exactly one distinct R-SIZE-002 warning.
    dual_002 = [f for f in size002 if _belongs(f, DUAL)]
    assert len(dual_002) == 1, f"expected one R-SIZE-002 for {DUAL}; got {size002!r}"
    finding = dual_002[0]
    assert _get(finding, "severity") == "warn"
    assert isinstance(_get(finding, "line"), int)

    message = str(_get(finding, "message"))
    lowered = message.lower()

    code_aliases = ["generated_code_loc", "generated code", "generated-code", "code_loc", "loc"]
    doc_aliases = ["component_doc_words", "component doc", "component-doc", "doc_words", "doc words"]
    assert any(a in lowered for a in code_aliases), f"code dimension not named: {message!r}"
    assert any(a in lowered for a in doc_aliases), f"doc-words dimension not named: {message!r}"

    # Current value of the generated-code dimension is named.
    assert re.search(rf"(?<!\d){LOC_LINES}(?!\d)", message), f"LOC value not named: {message!r}"

    # Points at SPEC_GUIDELINES.md Section 4.
    assert "SPEC_GUIDELINES.md" in message, f"guidelines not referenced: {message!r}"
    assert re.search(r"(§\s*4(?!\d)|section\s*4(?!\d))", message, re.IGNORECASE), (
        f"Section 4 not referenced: {message!r}"
    )

    # Every R-SIZE-002 finding belongs to the dual-dimension component only.
    for f in size002:
        assert _belongs(f, DUAL), f"stray R-SIZE-002 finding: {f!r}"