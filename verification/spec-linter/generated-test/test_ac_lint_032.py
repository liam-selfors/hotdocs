# hotdocs-criterion: sha256:3399afc699241ddf371c5ed4b90bc762e522d8c3b98bf5e4e9f2d9fae9195c05
import re
import shutil
from pathlib import Path

import pytest

import spec_linter


CLEAN_CORPUS = {
    'specs/product/foo.md': (
        '---\n'
        'id: P-FOO\n'
        'title: Foo works\n'
        'status: draft\n'
        'owners: [team-a]\n'
        '---\n'
        '\n'
        '# Foo works\n'
        '\n'
        '## Purpose\n'
        '\n'
        'A foo can be made.\n'
        '\n'
        '### CS-FOO-001\n'
        'Covers: P-FOO\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given nothing\n'
        'When a foo is made\n'
        'Then it exists\n'
        '```\n'
    ),
    'specs/components/foo/component.md': (
        '---\n'
        'id: comp-foo\n'
        'title: Foo\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: []\n'
        'realizes: [P-FOO]\n'
        'sealed: false\n'
        '---\n'
        '\n'
        '# Foo\n'
        '\n'
        '## Purpose\n'
        '\n'
        'Makes a foo.\n'
        '\n'
        '## Scope\n'
        '\n'
        '**In scope:** making a foo. **Out of scope:** everything else.\n'
        '\n'
        '## Definitions\n'
        '\n'
        'No deltas from `specs/glossary.md`.\n'
        '\n'
        '## Behavior\n'
        '\n'
        'See `requirements/`.\n'
        '\n'
        '## Interfaces\n'
        '\n'
        'See `interface/`.\n'
        '\n'
        '## Data\n'
        '\n'
        'None.\n'
        '\n'
        '## Acceptance criteria\n'
        '\n'
        'See `acceptance/`.\n'
        '\n'
        '## Non-functional constraints\n'
        '\n'
        'See `constraints.md`.\n'
        '\n'
        '## Open questions\n'
        '\n'
        'None.\n'
        '\n'
        '## Change log\n'
        '\n'
        '- Initial draft.\n'
    ),
    'specs/components/foo/requirements/R-FOO-001.md': (
        '# R-FOO-001\n'
        '\n'
        '**R-FOO-001** — `make_foo()` MUST return the string `"foo"`.\n'
    ),
    'specs/components/foo/interface/library.md': (
        '# Library\n'
        '\n'
        'One module file, `foo.py`.\n'
        '\n'
        '```\n'
        'make_foo() -> str\n'
        '```\n'
    ),
    'specs/components/foo/acceptance/AC-FOO-001.md': (
        '# AC-FOO-001\n'
        '\n'
        'Covers: R-FOO-001\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given nothing\n'
        'When make_foo() is called\n'
        'Then the result is "foo"\n'
        '```\n'
    ),
    'specs/components/foo/constraints.md': (
        '# Foo — Non-Functional Constraints\n'
        '\n'
        '- **Pure.** No I/O.\n'
    ),
}


def write_corpus(repo_root, changes=None):
    files = {**CLEAN_CORPUS, **(changes or {})}
    for rel, text in files.items():
        if text is not None:
            path = repo_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")


CACHE_MANAGER_FILES = {
    'specs/components/cache-manager/component.md': (
        '---\n'
        'id: comp-cache-manager\n'
        'title: Cache Manager\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: []\n'
        'realizes: [P-FOO]\n'
        'sealed: false\n'
        '---\n'
        '\n'
        '# Cache Manager\n'
        '\n'
        '## Purpose\n'
        '\n'
        'Manages a cache.\n'
        '\n'
        '## Scope\n'
        '\n'
        '**In scope:** caching. **Out of scope:** everything else.\n'
        '\n'
        '## Definitions\n'
        '\n'
        'No deltas from `specs/glossary.md`.\n'
        '\n'
        '## Behavior\n'
        '\n'
        'See `requirements/`.\n'
        '\n'
        '## Interfaces\n'
        '\n'
        'See `interface/`.\n'
        '\n'
        '## Data\n'
        '\n'
        'None.\n'
        '\n'
        '## Acceptance criteria\n'
        '\n'
        'See `acceptance/`.\n'
        '\n'
        '## Non-functional constraints\n'
        '\n'
        'See `constraints.md`.\n'
        '\n'
        '## Open questions\n'
        '\n'
        'None.\n'
        '\n'
        '## Change log\n'
        '\n'
        '- Initial draft.\n'
    ),
    'specs/components/cache-manager/requirements/R-CM-001.md': (
        '# R-CM-001\n'
        '\n'
        '**R-CM-001** — `get_cache()` MUST return the string `"cache"`.\n'
    ),
    'specs/components/cache-manager/interface/library.md': (
        '# Library\n'
        '\n'
        'One module file, `cache_manager.py`.\n'
        '\n'
        '```\n'
        'get_cache() -> str\n'
        '```\n'
    ),
    'specs/components/cache-manager/acceptance/AC-CM-001.md': (
        '# AC-CM-001\n'
        '\n'
        'Covers: R-CM-001\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given nothing\n'
        'When get_cache() is called\n'
        'Then the result is "cache"\n'
        '```\n'
    ),
    'specs/components/cache-manager/constraints.md': (
        '# Cache Manager — Non-Functional Constraints\n'
        '\n'
        '- **Pure.** No I/O.\n'
    ),
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def tool_root():
    """Parent of the nearest `gen` directory above the linter's own file, or None."""
    module_file = getattr(spec_linter, "__file__", None)
    if not module_file:
        return None
    for p in Path(module_file).resolve().parents:
        if p.name == "gen":
            return p.parent
    return None


@pytest.fixture
def tool_has_cache_manager():
    root = tool_root()
    if root is None:
        yield None
        return
    gen = root / "gen"
    target = gen / "cache-manager"
    created = False
    if not target.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        created = True
    try:
        yield target
    finally:
        if created and target.is_dir():
            shutil.rmtree(target, ignore_errors=True)


def build_project(repo_root, with_tool_marker):
    write_corpus(repo_root, CACHE_MANAGER_FILES)
    if with_tool_marker:
        (repo_root / ".hotdocs-tool.json").write_text("{}\n", encoding="utf-8")


def lint032(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-032"]


def test_project_component_shadowing_tool_component_fails(tmp_path, tool_has_cache_manager):
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    build_project(repo_root, with_tool_marker=True)

    report = spec_linter.lint(None, repo_root)

    if tool_has_cache_manager is None:
        pytest.skip("linter module is not under a gen/ directory; no tool root")
    root = tool_root()
    if (root / "gen" / "foo").is_dir():
        pytest.skip("tool root unexpectedly has gen/foo")

    findings = lint032(report)

    cm = [f for f in findings if "cache-manager" in str(field(f, "message"))]
    assert cm, "expected an R-LINT-032 finding naming cache-manager, got " + repr(findings)
    for f in cm:
        assert field(f, "severity") == "fail"

    for f in findings:
        message = str(field(f, "message")).replace("cache-manager", "")
        file = str(field(f, "file"))
        assert not re.search(r"\bfoo\b", message), (
            "foo must get no R-LINT-032 finding: " + repr(f)
        )
        assert "components/foo/" not in file, "foo must get no R-LINT-032 finding: " + repr(f)

    assert field(report, "hard_failures") >= 1


def test_project_without_tool_marker_has_no_finding(tmp_path, tool_has_cache_manager):
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    build_project(repo_root, with_tool_marker=False)

    report = spec_linter.lint(None, repo_root)
    assert lint032(report) == []


def test_tool_own_repository_has_no_finding(tmp_path):
    root = tool_root()
    if root is None or not (root / "specs").is_dir() or (root / ".hotdocs-tool.json").exists():
        # Still exercise the linter on a project without the marker.
        repo_root = tmp_path / "project"
        repo_root.mkdir()
        build_project(repo_root, with_tool_marker=False)
        report = spec_linter.lint(None, repo_root)
        assert lint032(report) == []
        pytest.skip("tool root has no lintable specs/ tree without .hotdocs-tool.json")
    report = spec_linter.lint(None, root)
    assert lint032(report) == []