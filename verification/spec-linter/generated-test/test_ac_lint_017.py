# hotdocs-criterion: sha256:5aaf20d0be252f9931bf76cb0bb344d85206f8d92cfd5ac5a6fe8605bda555d4
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


GUARANTEE_PATH = 'specs/components/foo/interface/guarantees/G-FOO-001.md'

MISMATCHED_GUARANTEE = (
    '# G-FOO-002\n'
    '\n'
    '**G-FOO-002** — `make_foo()` MUST always return the same value.\n'
)

MATCHING_GUARANTEE = (
    '# G-FOO-001\n'
    '\n'
    '**G-FOO-001** — `make_foo()` MUST always return the same value.\n'
)


def _lint017_fails(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-017" and field(f, "severity") == "fail"
    ]


def test_matching_guarantee_heading_has_no_lint017_failure(tmp_path):
    write_corpus(tmp_path, {GUARANTEE_PATH: MATCHING_GUARANTEE})
    report = spec_linter.lint(None, tmp_path)
    assert _lint017_fails(report) == []


def test_guarantee_heading_differing_from_filename_fails_lint017(tmp_path):
    write_corpus(tmp_path, {GUARANTEE_PATH: MISMATCHED_GUARANTEE})
    report = spec_linter.lint(None, tmp_path)
    fails = _lint017_fails(report)
    assert fails, "expected a fail-severity R-LINT-017 finding, got: " + repr(
        field(report, "findings")
    )
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith("G-FOO-001.md")
        for f in fails
    )
    assert field(report, "hard_failures") >= 1


def test_cli_reports_lint017_failure_and_exits_1(tmp_path, capsys):
    write_corpus(tmp_path, {GUARANTEE_PATH: MISMATCHED_GUARANTEE})
    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    assert any(
        f["rule_id"] == "R-LINT-017" and f["severity"] == "fail"
        for f in data["findings"]
    )