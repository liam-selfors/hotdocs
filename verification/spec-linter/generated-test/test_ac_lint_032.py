# hotdocs-criterion: sha256:93009b3bf3565c6a72709bcaf60673be52631f360d51c10cc976d12d9bcce559
import importlib.util
import re
import sys
from pathlib import Path

import spec_linter


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _linter():
    gen = next(p for p in Path(spec_linter.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter"), gen


def _tool_gen():
    return next(p for p in Path(spec_linter.__file__).resolve().parents if p.name == "gen")


def _shadow_slug():
    gen = _tool_gen()
    if (gen / "cache-manager").is_dir():
        return "cache-manager"
    # Fall back to a slug certain to exist under the tool's gen/.
    return "spec-linter"


COMPONENT_BODY = (
    "\n"
    "## Purpose\n\nA fixture component.\n\n"
    "## Scope\n\n- In scope: nothing.\n- Out of scope: everything.\n\n"
    "## Definitions\n\nNone.\n\n"
    "## Behavior\n\nSee `requirements/`.\n\n"
    "## Interfaces\n\nSee `interface/`.\n\n"
    "## Data\n\nSee `interface/data/`.\n\n"
    "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
    "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
    "## Open questions\n\n"
    "## Change log\n\n- Initial draft.\n"
)


def _write_component(repo_root, slug):
    d = repo_root / "specs" / "components" / slug
    (d / "requirements").mkdir(parents=True)
    (d / "acceptance").mkdir(parents=True)
    fm = (
        "---\n"
        "id: " + "comp-" + slug + "\n"
        "title: " + slug + "\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
    )
    (d / "component.md").write_text(fm + "\n# " + slug + "\n" + COMPONENT_BODY)
    (d / "constraints.md").write_text("# Constraints\n\nNone.\n")


def _build(repo_root, slugs, with_marker):
    (repo_root / "specs").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text("# Glossary\n\n- **Thing** — a thing.\n")
    for s in slugs:
        _write_component(repo_root, s)
    if with_marker:
        (repo_root / ".hotdocs-tool.json").write_text("{}\n")


def _findings_032(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-032"]


def test_shadowing_component_fails_and_other_does_not(tmp_path):
    linter, gen = _linter()
    shadow = _shadow_slug()
    assert (gen / shadow).is_dir()
    assert not (gen / "foo").exists()
    repo_root = tmp_path / "proj"
    _build(repo_root, ["foo", shadow], True)

    report = linter.lint(None, repo_root)
    found = _findings_032(report)
    assert found, "expected an R-LINT-032 finding for " + shadow
    named = [f for f in found if shadow in (field(f, "message") or "")]
    assert named
    for f in named:
        assert field(f, "severity") == "fail"
    for f in found:
        msg = field(f, "message") or ""
        fpath = field(f, "file") or ""
        assert not re.search(r"\bfoo\b", msg)
        assert "components/foo/" not in fpath


def test_no_finding_without_marker(tmp_path):
    linter, gen = _linter()
    shadow = _shadow_slug()
    repo_root = tmp_path / "proj"
    _build(repo_root, ["foo", shadow], False)
    report = linter.lint(None, repo_root)
    assert _findings_032(report) == []


def test_no_finding_on_tool_own_repository():
    linter, gen = _linter()
    tool_root = gen.parent
    if (tool_root / ".hotdocs-tool.json").exists():
        # The tool's own repository is not a hotdocs-init project.
        return
    report = linter.lint(None, tool_root)
    assert _findings_032(report) == []