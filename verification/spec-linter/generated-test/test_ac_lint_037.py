# hotdocs-criterion: sha256:168f80230ea7d36ac92eec4549fcf863490e80d10779921c520caee060586657
"""AC-LINT-037 (covers R-LINT-003): depends_on entries must resolve to an
existing, non-deprecated spec id."""

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


def _arch_doc(doc_id, title, status, depends_on=None):
    text = (
        '---\n'
        'id: ' + doc_id + '\n'
        'title: ' + title + '\n'
        'status: ' + status + '\n'
        'owners: [team-a]\n'
    )
    if depends_on is not None:
        text += 'depends_on: [' + ', '.join(depends_on) + ']\n'
    text += (
        '---\n'
        '\n'
        '# ' + title + '\n'
        '\n'
        '## Purpose\n'
        '\n'
        'An architecture document.\n'
    )
    return text


TARGET = 'specs/architecture/x.md'


def _norm(file_value):
    return str(file_value).replace('\\', '/')


def _is_target(file_value):
    f = _norm(file_value)
    return f == TARGET or f.endswith('/' + TARGET)


def test_ac_lint_037_depends_on_missing_and_deprecated_fail(tmp_path):
    repo_root = Path(tmp_path)
    write_corpus(repo_root, {
        TARGET: _arch_doc('arch-x', 'X', 'draft',
                          ['arch-gone', 'arch-old', 'arch-ok']),
        'specs/architecture/old.md': _arch_doc('arch-old', 'Old', 'deprecated'),
        'specs/architecture/ok.md': _arch_doc('arch-ok', 'Ok', 'draft'),
    })

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, 'findings'))

    ours = [
        f for f in findings
        if field(f, 'rule_id') == 'R-LINT-003'
        and field(f, 'severity') == 'fail'
        and _is_target(field(f, 'file'))
    ]
    messages = [str(field(f, 'message')) for f in ours]

    assert len(ours) == 2, messages

    gone = [m for m in messages if 'arch-gone' in m]
    old = [m for m in messages if 'arch-old' in m]
    assert len(gone) == 1, messages
    assert 'does not exist' in gone[0], messages
    assert len(old) == 1, messages
    assert gone[0] != old[0], messages

    assert not any('arch-ok' in m for m in messages), messages

    # No R-LINT-003 finding anywhere names arch-ok for this file.
    all_003_target = [
        str(field(f, 'message')) for f in findings
        if field(f, 'rule_id') == 'R-LINT-003' and _is_target(field(f, 'file'))
    ]
    assert not any('arch-ok' in m for m in all_003_target), all_003_target