import json
from pathlib import Path

import pytest

import spec_linter


RULE = "R-LINT-032"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _tool_root():
    here = Path(spec_linter.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen" and parent.is_dir():
            return parent.parent
    return None


def _component_md(slug):
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug} fixture\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}\n"
        "---\n"
        "\n"
        f"# {slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used only for testing.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: nothing.\n"
        "- Out of scope: everything.\n"
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


def _build_project(root, slugs, with_marker):
    root.mkdir(parents=True, exist_ok=True)
    specs = root / "specs"
    (specs / "components").mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Fixture** — a test-only term.\n", encoding="utf-8"
    )
    for slug in slugs:
        cdir = specs / "components" / slug
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "component.md").write_text(_component_md(slug), encoding="utf-8")
    if with_marker:
        (root / ".hotdocs-tool.json").write_text(json.dumps({}), encoding="utf-8")
    return root


def _rule_findings(report):
    findings = _get(report, "findings", None) or []
    return [f for f in findings if _get(f, "rule_id") == RULE]


def _text_of(finding):
    return f"{_get(finding, 'message', '') or ''} {_get(finding, 'file', '') or ''}"


def _pick_shadowing_slug(tool_root):
    gen = tool_root / "gen"
    if (gen / "cache-manager").is_dir():
        return "cache-manager"
    for child in sorted(gen.iterdir()):
        if child.is_dir() and not child.name.startswith(".") and child.name != "foo":
            return child.name
    return None


@pytest.fixture
def tool_root():
    root = _tool_root()
    if root is None:
        pytest.skip("linter is not installed under a gen/ directory")
    return root


def test_project_with_marker_flags_shadowing_component_only(tmp_path, tool_root):
    if (tool_root / "gen" / "foo").exists():
        pytest.skip("tool root unexpectedly has gen/foo")
    shadow = _pick_shadowing_slug(tool_root)
    if shadow is None:
        pytest.skip("tool root has no gen/ component directories")

    repo_root = _build_project(
        tmp_path.resolve() / "project", ["foo", shadow], with_marker=True
    )
    report = spec_linter.lint(None, repo_root)
    found = _rule_findings(report)

    shadow_findings = [f for f in found if shadow in _text_of(f)]
    assert shadow_findings, f"expected an {RULE} finding naming {shadow!r}, got {found!r}"
    for f in shadow_findings:
        assert _get(f, "severity") == "fail"
    assert any(shadow in (_get(f, "message", "") or "") for f in shadow_findings)

    foo_findings = [
        f for f in found
        if "'foo'" in _text_of(f)
        or '"foo"' in _text_of(f)
        or "/foo/" in _text_of(f)
        or _text_of(f).strip().endswith("foo")
        or " foo " in f" {_get(f, 'message', '') or ''} "
    ]
    assert not foo_findings, f"'foo' must get no {RULE} finding, got {foo_findings!r}"
    assert len(found) == 1, f"expected exactly one {RULE} finding, got {found!r}"

    hard = _get(report, "hard_failures")
    if hard is None and isinstance(report, dict):
        hard = (report.get("summary") or {}).get("hard_failures")
    if hard is not None:
        assert hard >= 1


def test_project_without_marker_has_no_finding(tmp_path, tool_root):
    shadow = _pick_shadowing_slug(tool_root) or "cache-manager"
    repo_root = _build_project(
        tmp_path.resolve() / "project", ["foo", shadow], with_marker=False
    )
    report = spec_linter.lint(None, repo_root)
    found = _rule_findings(report)
    assert found == [], f"no {RULE} finding expected without .hotdocs-tool.json, got {found!r}"


def test_marker_removed_after_finding_clears_it(tmp_path, tool_root):
    shadow = _pick_shadowing_slug(tool_root)
    if shadow is None:
        pytest.skip("tool root has no gen/ component directories")
    repo_root = _build_project(
        tmp_path.resolve() / "project", ["foo", shadow], with_marker=True
    )
    first = _rule_findings(spec_linter.lint(None, repo_root))
    assert first, f"expected an {RULE} finding while .hotdocs-tool.json is present"
    (repo_root / ".hotdocs-tool.json").unlink()
    second = _rule_findings(spec_linter.lint(None, repo_root))
    assert second == []


def test_tool_own_repository_has_no_finding(tool_root):
    if not (tool_root / "specs").is_dir():
        pytest.skip("tool root has no specs/ tree")
    report = spec_linter.lint(None, tool_root)
    found = _rule_findings(report)
    assert found == [], f"the tool's own repository must get no {RULE} finding, got {found!r}"