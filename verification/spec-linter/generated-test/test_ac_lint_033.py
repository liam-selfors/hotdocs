# hotdocs-criterion: sha256:6edc45ef6641c69e30841c4d56c17eef0f7486fa73912cc5eb31aa13e12da19c
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


COMPONENT_REL = 'specs/components/foo/component.md'


def _purpose_160_words():
    return ' '.join(['word'] * 160) + '.'


def _build_corpus(repo_root):
    original = CLEAN_CORPUS[COMPONENT_REL]
    text = original.replace(
        '## Purpose\n\nMakes a foo.\n',
        '## Purpose\n\n' + _purpose_160_words() + '\n',
    )
    assert text != original
    text = text.replace(
        '- Initial draft.\n',
        '- Initial draft, per `D999`.\n',
    )
    assert '`D999`' in text
    write_corpus(repo_root, {COMPONENT_REL: text})


def test_lint_includes_citation_and_size_findings(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)
    assert not (repo_root / 'specs' / 'decisions' / 'D999.md').exists()

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, 'findings'))

    cite = [
        (i, f) for i, f in enumerate(findings)
        if field(f, 'rule_id') == 'R-CITE-001'
    ]
    size = [
        (i, f) for i, f in enumerate(findings)
        if field(f, 'rule_id') == 'R-SIZE-004'
    ]
    assert len(cite) == 1, [field(f, 'rule_id') for f in findings]
    assert len(size) == 1, [field(f, 'rule_id') for f in findings]

    for _, f in cite + size:
        assert not isinstance(f, dict)
        assert type(f).__name__ == 'Finding'
        assert field(f, 'severity') == 'fail'
        assert str(field(f, 'file')).replace('\\', '/') == COMPONENT_REL

    # citation-checker's findings come before size-checker's
    assert cite[0][0] < size[0][0]

    assert field(report, 'hard_failures') == 2


def test_load_corpus_returns_corpus_with_component(tmp_path):
    repo_root = tmp_path
    _build_corpus(repo_root)

    load_corpus = spec_linter.load_corpus
    corpus = load_corpus(repo_root)

    assert type(corpus).__name__ == 'Corpus'
    components = field(corpus, 'components')
    assert 'foo' in components
    component = components['foo']
    assert type(component).__name__ == 'Component'
    root = field(component, 'root')
    assert root is not None
    assert field(root, 'rel_path') == COMPONENT_REL