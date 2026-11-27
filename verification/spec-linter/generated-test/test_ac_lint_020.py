# hotdocs-criterion: sha256:76665235ee9ec40c1b286b1029746e1dc252fbc97c753a11032741f409f8564c
import importlib.util
import sys
from pathlib import Path

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


FOO_ROOT = 'specs/components/foo/component.md'


def _bar_files():
    bar_root = (
        CLEAN_CORPUS[FOO_ROOT]
        .replace('id: comp-foo\n', 'id: comp-bar\n')
        .replace('title: Foo\n', 'title: Bar\n')
        .replace('# Foo\n', '# Bar\n')
        .replace('Makes a foo.\n', 'Makes a bar.\n')
        .replace('making a foo.', 'making a bar.')
    )
    return {
        'specs/components/bar/component.md': bar_root,
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
            '**G-BAR-001** — `make_bar()` MUST always return the same value.\n'
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


def _foo_root(depends_on):
    text = CLEAN_CORPUS[FOO_ROOT]
    assert 'depends_on: []\n' in text
    return text.replace(
        'depends_on: []\n',
        'depends_on: ' + depends_on + '\n' + 'depends_on_guarantees: [G-BAR-001]\n',
    )


def _r018_findings(report):
    return [
        f for f in field(report, 'findings')
        if field(f, 'rule_id') == 'R-LINT-018'
    ]


def test_guarantee_owner_not_in_depends_on_fails_r_lint_018(tmp_path):
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    changes = dict(_bar_files())
    changes[FOO_ROOT] = _foo_root('[]')
    write_corpus(repo_root, changes)

    report = spec_linter.lint(None, repo_root)

    r018 = _r018_findings(report)
    assert r018, 'expected an R-LINT-018 finding, got: ' + repr(field(report, 'findings'))
    fails = [f for f in r018 if field(f, 'severity') == 'fail']
    assert fails, 'expected R-LINT-018 at fail severity, got: ' + repr(r018)
    files = [str(field(f, 'file')).replace('\\', '/') for f in fails]
    assert any(p.endswith(FOO_ROOT) for p in files), files
    assert field(report, 'hard_failures') >= 1

    rc = spec_linter.main(['--repo-root=' + str(repo_root)])
    assert rc == 1


def test_control_guarantee_owner_listed_in_depends_on_passes_r_lint_018(tmp_path):
    # Same corpus, but comp-bar IS in depends_on: the guarantee resolves and
    # its owner (taken from its file's path) is a listed dependency.
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    changes = dict(_bar_files())
    changes[FOO_ROOT] = _foo_root('[comp-bar]')
    write_corpus(repo_root, changes)

    report = spec_linter.lint(None, repo_root)

    assert _r018_findings(report) == [], repr(_r018_findings(report))