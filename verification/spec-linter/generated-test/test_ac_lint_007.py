# hotdocs-criterion: sha256:a3c4cfdce293c745be2691459a40a3959ffc623458ad6590d41d6d90b5eea693
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


NO_KEYWORD_REQUIREMENT = (
    '# R-FOO-001\n'
    '\n'
    '**R-FOO-001** — `make_foo()` returns the string `"foo"`.\n'
)

CHANGES = {
    'specs/components/foo/requirements/R-FOO-001.md': NO_KEYWORD_REQUIREMENT,
}


def _lint_007_fails(findings):
    return [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-007" and field(f, "severity") == "fail"
    ]


def test_clean_corpus_has_no_r_lint_007_finding(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))
    assert not [f for f in findings if field(f, "rule_id") == "R-LINT-007"]
    assert field(report, "hard_failures") == 0


def test_requirement_without_rfc2119_keyword_fails_r_lint_007(tmp_path):
    write_corpus(tmp_path, CHANGES)
    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))
    matching = _lint_007_fails(findings)
    assert matching, (
        "expected a fail-severity R-LINT-007 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"))
                for f in findings])
    )
    assert field(report, "hard_failures") >= 1


def test_cli_reports_r_lint_007_fail_and_exits_1(tmp_path, capsys):
    write_corpus(tmp_path, CHANGES)
    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    matching = [
        f for f in doc["findings"]
        if f["rule_id"] == "R-LINT-007" and f["severity"] == "fail"
    ]
    assert matching
    assert doc["summary"]["hard_failures"] >= 1