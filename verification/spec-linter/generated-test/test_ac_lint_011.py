# hotdocs-criterion: sha256:264f71a9412eafbfa7a52cfa062df58e37e7ce1933c3ea31f32d7e08c9da2680
"""AC-LINT-011: a Definitions-section entry for a glossary term that is a
near-verbatim copy (token-overlap ratio >= 0.8) of the glossary's own
definition yields a fail-severity finding for R-LINT-011."""

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


GLOSSARY_DEFINITION = (
    'a small reusable unit of foo that the pipeline assembles into a '
    'larger bar during every generation run'
)

GLOSSARY = (
    '# Glossary\n'
    '\n'
    'Canonical vocabulary for this spec corpus.\n'
    '\n'
    '- **Widget** — ' + GLOSSARY_DEFINITION + '.\n'
)


def component_with_definitions(definitions_body):
    original = CLEAN_CORPUS['specs/components/foo/component.md']
    old = '## Definitions\n\nNo deltas from `specs/glossary.md`.\n'
    assert old in original
    return original.replace(old, '## Definitions\n\n' + definitions_body + '\n')


def r011_findings(report):
    return [
        f for f in field(report, 'findings')
        if field(f, 'rule_id') == 'R-LINT-011'
    ]


def test_near_verbatim_definition_fails_r_lint_011(tmp_path):
    repo_root = tmp_path
    # Near-verbatim: identical wording, only one word changed ("every" -> "each").
    local = (
        'a small reusable unit of foo that the pipeline assembles into a '
        'larger bar during each generation run'
    )
    write_corpus(repo_root, {
        'specs/glossary.md': GLOSSARY,
        'specs/components/foo/component.md': component_with_definitions(
            '- **Widget** — ' + local + '.\n'
        ),
    })

    report = spec_linter.lint(None, repo_root)

    found = r011_findings(report)
    assert found, (
        'expected an R-LINT-011 finding, got: '
        + repr([(field(f, 'rule_id'), field(f, 'severity'), field(f, 'message'))
                for f in field(report, 'findings')])
    )
    assert any(field(f, 'severity') == 'fail' for f in found)
    assert field(report, 'hard_failures') >= 1


def test_exact_copy_definition_fails_r_lint_011(tmp_path):
    repo_root = tmp_path
    write_corpus(repo_root, {
        'specs/glossary.md': GLOSSARY,
        'specs/components/foo/component.md': component_with_definitions(
            '- **Widget** — ' + GLOSSARY_DEFINITION + '.\n'
        ),
    })

    report = spec_linter.lint(None, repo_root)

    found = r011_findings(report)
    assert any(field(f, 'severity') == 'fail' for f in found)


def test_no_definitions_entry_has_no_r_lint_011(tmp_path):
    repo_root = tmp_path
    write_corpus(repo_root, {'specs/glossary.md': GLOSSARY})

    report = spec_linter.lint(None, repo_root)

    assert r011_findings(report) == []


def test_dissimilar_definition_has_no_r_lint_011(tmp_path):
    repo_root = tmp_path
    write_corpus(repo_root, {
        'specs/glossary.md': GLOSSARY,
        'specs/components/foo/component.md': component_with_definitions(
            '- **Widget** — here, additionally, only ever produced by '
            '`make_foo()` and never cached across runs.\n'
        ),
    })

    report = spec_linter.lint(None, repo_root)

    assert not any(
        field(f, 'severity') == 'fail' for f in r011_findings(report)
    )