# hotdocs-criterion: sha256:07655f08ec2d95c39fc020ac3aba6201a3ee1f47cf4a57c9f507ca2cb0b303e8
"""AC-LINT-004: a depends_on cycle (A -> B -> A) is a fail-severity
R-LINT-004 finding naming both components by their comp-<slug> ids."""

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


def _component_md(comp_id, title, depends_on):
    return (
        '---\n'
        'id: ' + comp_id + '\n'
        'title: ' + title + '\n'
        'status: draft\n'
        'owners: [team-a]\n'
        'depends_on: [' + depends_on + ']\n'
        'realizes: [P-FOO]\n'
        'sealed: false\n'
        '---\n'
        '\n'
        '# ' + title + '\n'
        '\n'
        '## Purpose\n'
        '\n'
        'Makes a ' + title.lower() + '.\n'
        '\n'
        '## Scope\n'
        '\n'
        '**In scope:** making a thing. **Out of scope:** everything else.\n'
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
    )


CYCLE_CHANGES = {
    'specs/components/foo/component.md': _component_md('comp-foo', 'Foo', 'comp-bar'),
    'specs/components/bar/component.md': _component_md('comp-bar', 'Bar', 'comp-foo'),
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


def _cycle_findings(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-004"
    ]


def test_clean_corpus_has_no_cycle_finding(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert _cycle_findings(report) == []


def test_two_component_cycle_is_fail_finding_naming_both(tmp_path):
    write_corpus(tmp_path, CYCLE_CHANGES)

    report = spec_linter.lint(None, tmp_path)

    cycle = _cycle_findings(report)
    assert cycle, "expected an R-LINT-004 finding, got: " + repr(field(report, "findings"))

    naming_both = [
        f for f in cycle
        if field(f, "severity") == "fail"
        and "comp-foo" in field(f, "message")
        and "comp-bar" in field(f, "message")
    ]
    assert naming_both, (
        "expected a fail-severity R-LINT-004 finding naming comp-foo and comp-bar, got: "
        + repr(cycle)
    )
    assert field(report, "hard_failures") >= 1