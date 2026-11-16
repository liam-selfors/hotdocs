"""AC-LINT-033 (Covers: R-LINT-033).

lint() folds citation-checker's and size-checker's findings into its own
report as Finding objects, and load_corpus is corpus-loader's function,
re-exported unchanged.
"""

import dataclasses
from pathlib import Path

import spec_linter


COMPONENT_REL = "specs/components/foo/component.md"
SENTENCE = "This component returns a fixed value to every caller always."  # 10 words


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path, purpose_text: str, rationale_text: str) -> None:
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose_text}\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"{rationale_text}\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: returning a fixed value.\n"
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
        "- Initial draft.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo` MUST return the integer 1.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When foo() runs\n"
        "Then it returns 1\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo() -> int\n```\n\nReturns the integer 1.\n",
    )
    _write(
        comp / "interface" / "data" / "Value.md",
        "# `Value`\n\nA plain integer.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n"
        "- Latency: a call completes in under 1 second, measured by timing one call.\n",
    )
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing used only by this fixture.\n",
    )


def _broken_corpus(repo_root: Path) -> None:
    purpose = " ".join([SENTENCE] * 16)
    assert len(purpose.split()) == 160
    _build_corpus(
        repo_root,
        purpose,
        "No further history applies. This design follows `D999`.",
    )


def _is_finding(value) -> bool:
    if isinstance(value, dict):
        return False
    finding_cls = getattr(spec_linter, "Finding", None)
    if finding_cls is not None:
        return isinstance(value, finding_cls)
    return dataclasses.is_dataclass(value) and type(value).__name__ == "Finding"


def _same_file(file_value, repo_root: Path) -> bool:
    text = str(file_value).replace("\\", "/")
    if text == COMPONENT_REL:
        return True
    p = Path(str(file_value))
    if p.is_absolute():
        try:
            return p.resolve() == (repo_root / COMPONENT_REL).resolve()
        except OSError:
            return False
    return False


def test_clean_baseline_has_no_hard_failures(tmp_path):
    repo_root = tmp_path / "clean"
    repo_root.mkdir()
    _build_corpus(repo_root, " ".join([SENTENCE] * 3), "No further history applies.")
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    fails = [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in field(report, "findings")
        if field(f, "severity") == "fail"
    ]
    assert hard == 0, fails


def test_lint_includes_citation_and_size_checker_findings(tmp_path):
    repo_root = tmp_path / "broken"
    repo_root.mkdir()
    _broken_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    summary = [
        (field(f, "rule_id"), field(f, "severity"), str(field(f, "file")), field(f, "message"))
        for f in findings
    ]

    cite = [
        f
        for f in findings
        if field(f, "rule_id") == "R-CITE-001" and field(f, "severity") == "fail"
    ]
    size = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-004" and field(f, "severity") == "fail"
    ]

    assert len(cite) >= 1, summary
    assert len(size) >= 1, summary

    cite_on_file = [f for f in cite if _same_file(field(f, "file"), repo_root)]
    size_on_file = [f for f in size if _same_file(field(f, "file"), repo_root)]
    assert cite_on_file, summary
    assert size_on_file, summary

    for f in cite_on_file + size_on_file:
        assert _is_finding(f), (type(f), f)

    assert any("D999" in str(field(f, "message")) for f in cite_on_file), summary

    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 2, summary


def test_load_corpus_returns_corpus_with_component(tmp_path):
    repo_root = tmp_path / "broken"
    repo_root.mkdir()
    _broken_corpus(repo_root)

    load_corpus = spec_linter.load_corpus
    assert callable(load_corpus)
    assert getattr(load_corpus, "__name__", None) == "load_corpus"

    corpus = load_corpus(repo_root)
    assert type(corpus).__name__ == "Corpus"
    components = field(corpus, "components")
    assert "foo" in components, list(components)
    comp = components["foo"]
    assert type(comp).__name__ == "Component"
    assert field(comp, "name") == "foo"