# hotdocs-criterion: sha256:0b5023d6cd04a1c44e77d7631b0d9b5c42aad2f1c71c8b91d7a2eaa3c704fce5
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_REL = 'specs/components/foo/component.md'


def component_with_drivers(drivers_line):
    text = CLEAN_CORPUS[COMPONENT_REL]
    marker = 'depends_on: []\n'
    assert marker in text
    return text.replace(marker, marker + drivers_line + '\n', 1)


def drivers_line_number(text):
    for index, line in enumerate(text.splitlines(), start=1):
        if line.startswith('drivers:'):
            return index
    raise AssertionError('no drivers line')


def norm(path):
    return str(path).replace('\\', '/')


def findings_on_line(report, rel, line):
    out = []
    for finding in field(report, 'findings'):
        if norm(field(finding, 'file')) == rel and field(finding, 'line') == line:
            out.append(finding)
    return out


DRIVER_DEFINITION = (
    '---\n'
    'id: arch-test-driver-mine\n'
    'title: Test Driver mine\n'
    'status: draft\n'
    'owners: [team-a]\n'
    'depends_on: []\n'
    '---\n'
    '\n'
    '# Test Driver mine\n'
    '\n'
    '## Purpose\n'
    '\n'
    'A test driver defined in this repository.\n'
)


def test_clean_corpus_is_lint_clean(tmp_path):
    repo_root = tmp_path / 'repo'
    write_corpus(repo_root)
    report = spec_linter.lint(None, repo_root)
    assert field(report, 'hard_failures') == 0


@pytest.mark.parametrize(
    'item, extra, expected_message',
    [
        (
            'Bad_Name',
            {},
            "driver 'Bad_Name' is not a driver name",
        ),
        (
            'nodrv',
            {},
            "test driver 'nodrv' has no definition or adapter",
        ),
        (
            'mine',
            {'specs/architecture/test-driver-mine.md': DRIVER_DEFINITION},
            "test driver 'mine' is defined in this repository; "
            "depends_on must list comp-driver-mine",
        ),
    ],
)
def test_bad_driver_item_gives_exactly_one_fail_on_drivers_line(
    tmp_path, item, extra, expected_message
):
    repo_root = tmp_path / 'repo'
    text = component_with_drivers('drivers: [' + item + ']')
    changes = {COMPONENT_REL: text}
    changes.update(extra)
    write_corpus(repo_root, changes)

    line = drivers_line_number(text)
    report = spec_linter.lint(None, repo_root)
    on_line = findings_on_line(report, COMPONENT_REL, line)
    fails = [f for f in on_line if field(f, 'severity') == 'fail']

    assert len(fails) == 1, [
        (field(f, 'severity'), field(f, 'message')) for f in on_line
    ]
    assert field(fails[0], 'message') == expected_message


def test_driver_with_planted_adapter_and_no_definition_has_no_finding(tmp_path):
    repo_root = tmp_path / 'repo'
    text = component_with_drivers('drivers: [fake]')
    write_corpus(repo_root, {COMPONENT_REL: text})

    adapter = repo_root / 'gen' / 'driver-fake' / 'driver_fake.py'
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text('DRIVER = ' + repr('fake') + '\n', encoding='utf-8')
    assert not (repo_root / 'specs' / 'architecture' / 'test-driver-fake.md').exists()

    line = drivers_line_number(text)
    report = spec_linter.lint(None, repo_root)
    on_line = findings_on_line(report, COMPONENT_REL, line)

    assert on_line == [], [
        (field(f, 'severity'), field(f, 'message')) for f in on_line
    ]