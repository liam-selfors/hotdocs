# hotdocs-criterion: sha256:c484d5ec82c18f08c2ed8640ed608570b88ddb5bc5f526dc139c4eacd27f1088
import re
import shutil
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_gen():
    return next(
        p for p in Path(spec_linter.__file__).resolve().parents if p.name == "gen"
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug + " component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used for testing.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: nothing.\n"
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


def _build_project(repo_root, with_tool_marker):
    for slug in ("foo", "cache-manager"):
        _write(repo_root / "specs" / "components" / slug / "component.md", _component_md(slug))
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a fixture term.\n",
    )
    if with_tool_marker:
        _write(repo_root / ".hotdocs-tool.json", "{}\n")


def _lint032(repo_root):
    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-032"]


def _names_slug(finding, slug, repo_root):
    text = str(field(finding, "message")) + " " + str(field(finding, "file"))
    text = text.replace(str(repo_root), "")
    pattern = r"(?<![\w-])" + re.escape(slug) + r"(?![\w-])"
    return re.search(pattern, text) is not None


def test_ac_lint_032_project_component_shadowing_tool_component(tmp_path):
    tool_gen = _tool_gen()
    tool_root = tool_gen.parent
    cache_dir = tool_gen / "cache-manager"
    created = False
    if not cache_dir.is_dir():
        cache_dir.mkdir()
        created = True
    try:
        assert not (tool_gen / "foo").is_dir()

        repo_root = tmp_path / "proj"
        repo_root.mkdir()
        _build_project(repo_root, with_tool_marker=True)

        found = _lint032(repo_root)
        cache_fails = [
            f
            for f in found
            if field(f, "severity") == "fail" and _names_slug(f, "cache-manager", repo_root)
        ]
        assert len(cache_fails) >= 1, found
        foo_findings = [f for f in found if _names_slug(f, "foo", repo_root)]
        assert foo_findings == [], foo_findings

        # Same project without .hotdocs-tool.json: no R-LINT-032 finding.
        (repo_root / ".hotdocs-tool.json").unlink()
        assert _lint032(repo_root) == []

        # The tool's own repository: no R-LINT-032 finding.
        if (tool_root / "specs").is_dir() and not (tool_root / ".hotdocs-tool.json").exists():
            assert _lint032(tool_root) == []
    finally:
        if created:
            shutil.rmtree(cache_dir, ignore_errors=True)