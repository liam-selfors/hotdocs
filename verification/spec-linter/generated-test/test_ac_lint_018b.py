# hotdocs-criterion: sha256:e412ff0deea0b373360e4c02bfbb0d399384e591ebc374c516ab3be8bbe93619
import json

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


COMPONENT_PATH = 'specs/components/foo/component.md'


def _component_with_bad_guarantee():
    original = CLEAN_CORPUS[COMPONENT_PATH]
    needle = 'depends_on: []\n'
    assert needle in original
    return original.replace(
        needle, needle + 'depends_on_guarantees: [G-DOES-NOT-EXIST]\n', 1
    )


def _r018_fails(findings):
    return [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-018" and field(f, "severity") == "fail"
    ]


def test_clean_corpus_has_no_hard_failures(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert field(report, "hard_failures") == 0


def test_unresolved_guarantee_gives_r_lint_018_fail_via_library(tmp_path):
    write_corpus(tmp_path, {COMPONENT_PATH: _component_with_bad_guarantee()})

    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))

    matching = _r018_fails(findings)
    assert matching, (
        "expected a fail-severity R-LINT-018 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "message"))
                for f in findings])
    )
    assert field(report, "hard_failures") >= 1


def test_unresolved_guarantee_gives_r_lint_018_fail_via_cli(tmp_path, capsys):
    write_corpus(tmp_path, {COMPONENT_PATH: _component_with_bad_guarantee()})

    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    matching = _r018_fails(doc["findings"])
    assert matching, "expected a fail-severity R-LINT-018 finding in: " + repr(doc)
    assert doc["summary"]["hard_failures"] >= 1