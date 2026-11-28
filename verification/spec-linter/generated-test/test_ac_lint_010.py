# hotdocs-criterion: sha256:06a6f2a77a65b73f672658d59ae87070c047d009f086e7aeaf3ab91e56c81a91
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


AC_PATH = 'specs/components/foo/acceptance/AC-FOO-001.md'
NO_KIND_AC = (
    '# AC-FOO-001\n'
    '\n'
    'Covers: R-FOO-001\n'
    '\n'
    '```gherkin\n'
    'Given nothing\n'
    'When make_foo() is called\n'
    'Then the result is "foo"\n'
    '```\n'
)
EXPECTED_MESSAGE = (
    'AC-FOO-001 has no Kind: line (compiled, generated-test or llm-judge)'
)


def test_clean_corpus_has_no_r_lint_010(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert field(report, "hard_failures") == 0
    assert not [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-010"
    ]


def test_missing_kind_gives_fail_finding_for_r_lint_010(tmp_path):
    write_corpus(tmp_path, {AC_PATH: NO_KIND_AC})
    report = spec_linter.lint(None, tmp_path)
    findings = field(report, "findings")

    lint010 = [f for f in findings if field(f, "rule_id") == "R-LINT-010"]
    assert len(lint010) == 1, findings
    finding = lint010[0]
    assert field(finding, "severity") == "fail"
    assert field(finding, "file") == AC_PATH
    assert field(finding, "line") == 1
    assert field(finding, "message") == EXPECTED_MESSAGE

    fails = [f for f in findings if field(f, "severity") == "fail"]
    assert len(fails) == 1, findings
    assert field(report, "hard_failures") == 1


def test_missing_kind_via_cli_json_report(tmp_path, capsys):
    write_corpus(tmp_path, {AC_PATH: NO_KIND_AC})
    code = spec_linter.main(
        ["--format=json", "--repo-root=" + str(tmp_path)]
    )
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    lint010 = [
        f for f in data["findings"]
        if f["rule_id"] == "R-LINT-010"
    ]
    assert len(lint010) == 1, data
    assert lint010[0]["severity"] == "fail"
    assert lint010[0]["file"] == AC_PATH
    assert lint010[0]["line"] == 1
    assert lint010[0]["message"] == EXPECTED_MESSAGE
    assert data["summary"]["hard_failures"] == 1