# hotdocs-criterion: sha256:c238eec51bd366e6a140e96293bae0990447efd73a7811f0ce8a1d1436af638b
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


def _r008_findings(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-008"]


def _names(finding, req_id):
    message = field(finding, "message") or ""
    file = field(finding, "file") or ""
    return req_id in str(message) or req_id in str(file)


def test_clean_corpus_has_no_forward_traceability_finding(tmp_path):
    write_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)
    assert _r008_findings(report) == []


def test_requirement_with_no_covering_criterion_fails(tmp_path):
    write_corpus(
        tmp_path,
        {'specs/components/foo/acceptance/AC-FOO-001.md': None},
    )
    report = spec_linter.lint(None, tmp_path)
    matching = [
        f for f in _r008_findings(report)
        if field(f, "severity") == "fail" and _names(f, "R-FOO-001")
    ]
    assert matching, [
        (field(f, "rule_id"), field(f, "severity"), field(f, "message"))
        for f in field(report, "findings")
    ]
    assert field(report, "hard_failures") >= 1


def test_criterion_covering_another_requirement_does_not_count(tmp_path):
    write_corpus(
        tmp_path,
        {
            'specs/components/foo/requirements/R-FOO-002.md': (
                '# R-FOO-002\n'
                '\n'
                '**R-FOO-002** — `make_foo()` MUST NOT raise.\n'
            ),
        },
    )
    report = spec_linter.lint(None, tmp_path)
    r008 = _r008_findings(report)
    assert any(
        field(f, "severity") == "fail" and _names(f, "R-FOO-002") for f in r008
    ), [(field(f, "rule_id"), field(f, "message")) for f in field(report, "findings")]
    # R-FOO-001 is still covered by AC-FOO-001, so it is not reported.
    assert not any(
        _names(f, "R-FOO-001") and not _names(f, "R-FOO-002") for f in r008
    )


def test_cli_json_reports_r_lint_008_and_exits_1(tmp_path, capsys):
    write_corpus(
        tmp_path,
        {'specs/components/foo/acceptance/AC-FOO-001.md': None},
    )
    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    assert any(
        f["rule_id"] == "R-LINT-008"
        and f["severity"] == "fail"
        and ("R-FOO-001" in f["message"] or "R-FOO-001" in f["file"])
        for f in data["findings"]
    )
    assert data["summary"]["hard_failures"] >= 1