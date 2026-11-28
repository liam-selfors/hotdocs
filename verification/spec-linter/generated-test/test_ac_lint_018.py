# hotdocs-criterion: sha256:d74bd70337ccf49dfbee7e6e6cea49940ca197c05988072bb3e8f26fc5db4ff4
"""AC-LINT-018: a depends_on_guarantees entry whose owning component is not
listed in depends_on yields a fail-severity R-LINT-018 finding naming the
owning component by its comp-<slug> id."""

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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BAR_FILES = {
    'specs/components/bar/component.md': (
        '---\n'
        'id: comp-bar\n'
        'title: Bar\n'
        'status: draft\n'
        'owners: [team-b]\n'
        'depends_on: []\n'
        'sealed: true\n'
        'source_path: legacy/bar/\n'
        '---\n'
        '\n'
        '# Bar\n'
        '\n'
        '## Purpose\n'
        '\n'
        'Makes a bar.\n'
        '\n'
        '## Scope\n'
        '\n'
        '**In scope:** making a bar. **Out of scope:** everything else.\n'
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
    'specs/components/bar/requirements/R-BAR-001.md': (
        '# R-BAR-001\n'
        '\n'
        '**R-BAR-001** — `make_bar()` MUST return the string `"bar"`.\n'
    ),
    'specs/components/bar/interface/library.md': (
        '# Library\n'
        '\n'
        'One module file, `bar.py`.\n'
        '\n'
        '```\n'
        'make_bar() -> str\n'
        '```\n'
    ),
    'specs/components/bar/interface/guarantees/G-BAR-001.md': (
        '# G-BAR-001\n'
        '\n'
        '**G-BAR-001** — `make_bar()` MUST be idempotent.\n'
    ),
    'specs/components/bar/acceptance/AC-BAR-001.md': (
        '# AC-BAR-001\n'
        '\n'
        'Covers: R-BAR-001\n'
        'Kind: generated-test\n'
        '\n'
        '```gherkin\n'
        'Given nothing\n'
        'When make_bar() is called\n'
        'Then the result is "bar"\n'
        '```\n'
    ),
    'specs/components/bar/constraints.md': (
        '# Bar — Non-Functional Constraints\n'
        '\n'
        '- **Pure.** No I/O.\n'
    ),
}


def _foo_component(depends_on_line):
    original = CLEAN_CORPUS['specs/components/foo/component.md']
    assert 'depends_on: []\n' in original
    return original.replace(
        'depends_on: []\n',
        depends_on_line + 'depends_on_guarantees: [G-BAR-001]\n',
        1,
    )


def _r018_findings(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-018"]


def test_missing_owning_dependency_is_fail_naming_comp_bar(tmp_path):
    changes = dict(BAR_FILES)
    changes['specs/components/foo/component.md'] = _foo_component('depends_on: []\n')
    write_corpus(tmp_path, changes)

    report = spec_linter.lint(None, tmp_path)

    r018 = _r018_findings(report)
    matching = [
        f for f in r018
        if field(f, "severity") == "fail" and "comp-bar" in field(f, "message")
    ]
    assert matching, (
        "expected a fail-severity R-LINT-018 finding naming comp-bar, got: "
        + repr([(field(f, "severity"), field(f, "message")) for f in field(report, "findings")])
    )
    assert report.hard_failures >= 1

    exit_code = spec_linter.main(["--repo-root", str(tmp_path)])
    assert exit_code == 1


def test_listed_owning_dependency_gives_no_r018_finding(tmp_path):
    changes = dict(BAR_FILES)
    changes['specs/components/foo/component.md'] = _foo_component('depends_on: [comp-bar]\n')
    write_corpus(tmp_path, changes)

    report = spec_linter.lint(None, tmp_path)

    r018 = _r018_findings(report)
    assert r018 == [], repr([field(f, "message") for f in r018])