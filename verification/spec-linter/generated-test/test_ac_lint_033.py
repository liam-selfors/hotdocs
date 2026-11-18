# hotdocs-criterion: sha256:01a445c3cb51513fee68906229ba1414e124bcb4dc27e37918c3d1d02714e4ae
import json
from pathlib import Path

import spec_linter


COMPONENT_REL = "specs/components/widget/component.md"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _norm_str(value):
    inner = getattr(value, "value", value)
    return str(inner)


def _norm_path(value):
    return str(value).replace("\\", "/")


def _purpose_text():
    sentence = "This component formats widget records into stable plain text output."
    words = (sentence + " ") * 16
    tokens = words.split()
    assert len(tokens) == 160
    return " ".join(tokens)


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path):
    comp_dir = repo_root / "specs" / "components" / "widget"
    component_md = (
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/widget.py\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        + _purpose_text()
        + "\n"
        "\n"
        "## Rationale\n"
        "\n"
        "This design follows D999.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: formatting widget records.\n"
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
    _write(comp_dir / "component.md", component_md)
    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget MUST format each record as plain text.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a record\n"
        "When the widget formats it\n"
        "Then the output is plain text\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nformat(record: dict) -> str\n```\n\nFormats a record as plain text.\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- Formatting one record takes under 10 ms, measured by a timing test.\n",
    )
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Gizmo** — an unrelated example term.\n",
    )


def _write_fake_checker(repo_root: Path, slug: str, module_name: str, finding: dict, log_path: Path):
    source = (
        "import json\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_FINDING = " + repr(finding) + "\n"
        "\n"
        "def check(repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'module': " + repr(module_name) + ", 'repo_root': str(repo_root)}) + '\\n')\n"
        "    return [dict(_FINDING)]\n"
    )
    _write(repo_root / "gen" / slug / (module_name + ".py"), source)


CITE_FINDING = {
    "rule_id": "R-CITE-001",
    "severity": "fail",
    "file": COMPONENT_REL,
    "line": 17,
    "message": "cites D999, which has no decision file",
}

SIZE_FINDING = {
    "rule_id": "R-SIZE-004",
    "severity": "fail",
    "file": COMPONENT_REL,
    "line": 12,
    "message": "Purpose section is 160 words, above the 150-word hard cap",
}


def _setup(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    log_path = tmp_path / "checker_calls.log"
    _write_fake_checker(repo_root, "citation-checker", "citation_checker", CITE_FINDING, log_path)
    _write_fake_checker(repo_root, "size-checker", "size_checker", SIZE_FINDING, log_path)
    return repo_root, log_path


def _hard_failures(report):
    value = _get(report, "hard_failures", None)
    if value is None:
        summary = _get(report, "summary", None)
        if summary is not None:
            value = _get(summary, "hard_failures", None)
    return value


def _is_finding(obj):
    finding_cls = getattr(spec_linter, "Finding", None)
    if isinstance(finding_cls, type):
        return isinstance(obj, finding_cls)
    return type(obj).__name__ == "Finding"


def test_lint_includes_citation_and_size_checker_findings_as_findings(tmp_path):
    repo_root, log_path = _setup(tmp_path)

    report = spec_linter.lint(None, repo_root)

    findings = list(_get(report, "findings", []) or [])

    cite = [f for f in findings if _norm_str(_get(f, "rule_id")) == "R-CITE-001"]
    size = [f for f in findings if _norm_str(_get(f, "rule_id")) == "R-SIZE-004"]

    assert len(cite) == 1, findings
    assert len(size) == 1, findings

    for found, expected in ((cite[0], CITE_FINDING), (size[0], SIZE_FINDING)):
        assert _is_finding(found), type(found)
        assert not isinstance(found, dict)
        assert _norm_str(_get(found, "severity")) == "fail"
        assert _norm_path(_get(found, "file")) == COMPONENT_REL
        assert _get(found, "line") == expected["line"]
        assert _get(found, "message") == expected["message"]

    # citation-checker's findings come before size-checker's
    assert findings.index(cite[0]) < findings.index(size[0])

    assert _hard_failures(report) == 2

    # Both dependency checkers really ran, against this repo_root
    assert log_path.exists()
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    modules = [r["module"] for r in records]
    assert "citation_checker" in modules
    assert "size_checker" in modules
    for r in records:
        assert Path(r["repo_root"]).resolve() == repo_root.resolve()


def test_load_corpus_returns_corpus_with_component(tmp_path):
    repo_root, _ = _setup(tmp_path)

    assert callable(getattr(spec_linter, "load_corpus", None))
    corpus = spec_linter.load_corpus(repo_root)

    assert type(corpus).__name__ == "Corpus"
    components = _get(corpus, "components", None)
    assert components is not None
    assert "widget" in components