# hotdocs-criterion: sha256:b051479f62ab625193a4e15905f71078755f2f186453538124ef2bc83a05a81c
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


TARGET_REL = 'specs/components/foo/requirements/R-FOO-001.md'


def _norm(p):
    return str(p).replace('\\', '/')


def _r019(report):
    return [f for f in field(report, 'findings') if field(f, 'rule_id') == 'R-LINT-019']


def test_clean_corpus_has_no_trailing_whitespace_finding(tmp_path):
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    write_corpus(repo_root)
    report = spec_linter.lint(None, repo_root)
    assert _r019(report) == []


def test_trailing_two_spaces_reports_fail_finding_on_that_line(tmp_path):
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    changed = (
        '# R-FOO-001\n'
        '\n'
        '**R-FOO-001** — `make_foo()` MUST return the string `"foo"`.  \n'
    )
    write_corpus(repo_root, {TARGET_REL: changed})

    report = spec_linter.lint(None, repo_root)
    findings = _r019(report)

    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, 'severity') == 'fail'
    file_value = _norm(field(finding, 'file'))
    assert file_value == TARGET_REL or file_value.endswith('/' + TARGET_REL)
    assert field(finding, 'line') == 3
    assert field(report, 'hard_failures') >= 1


def test_trailing_spaces_in_frontmatter_also_fail(tmp_path):
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    rel = 'specs/components/foo/component.md'
    original = CLEAN_CORPUS[rel]
    changed = original.replace('title: Foo\n', 'title: Foo  \n', 1)
    assert changed != original
    write_corpus(repo_root, {rel: changed})

    report = spec_linter.lint(None, repo_root)
    findings = _r019(report)

    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, 'severity') == 'fail'
    file_value = _norm(field(finding, 'file'))
    assert file_value == rel or file_value.endswith('/' + rel)
    assert field(finding, 'line') == 3


def test_cli_exits_1_on_trailing_whitespace(tmp_path, capsys):
    repo_root = tmp_path / 'repo'
    repo_root.mkdir()
    changed = (
        '# R-FOO-001\n'
        '\n'
        '**R-FOO-001** — `make_foo()` MUST return the string `"foo"`.  \n'
    )
    write_corpus(repo_root, {TARGET_REL: changed})
    code = spec_linter.main(['--format=json', '--repo-root=' + str(repo_root)])
    assert code == 1