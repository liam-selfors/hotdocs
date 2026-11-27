# hotdocs-criterion: sha256:db7356b154ddedf488bc0511dd2297710e58d5742b59b0ede578f43e2baeecfb
import json
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


VAR_PATH = 'specs/vars/VAR-API-TOKEN.md'


def var_text(sensitivity):
    return (
        '---\n'
        'id: VAR-API-TOKEN\n'
        'title: API token\n'
        'status: draft\n'
        'owners: [team-a]\n'
        '---\n'
        '\n'
        '# API token\n'
        '\n'
        '- name: VAR-API-TOKEN\n'
        '- required\n'
        '- type: secret-ref\n'
        '- description: The token used to call the API.\n'
        '- sensitivity: ' + sensitivity + '\n'
        '- default: abc123\n'
    )


def lint_013_fails(report):
    findings = field(report, "findings")
    return [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-013" and field(f, "severity") == "fail"
    ]


def test_secret_var_with_default_fails_r_lint_013(tmp_path):
    repo_root = tmp_path
    write_corpus(repo_root, {VAR_PATH: var_text('secret')})

    report = spec_linter.lint(None, repo_root)

    matches = lint_013_fails(report)
    assert matches, "expected a fail-severity R-LINT-013 finding, got: " + repr(
        field(report, "findings")
    )
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith(VAR_PATH) for f in matches
    )
    assert field(report, "hard_failures") >= 1


def test_secret_var_with_default_cli_json_reports_r_lint_013(tmp_path, capsys):
    repo_root = tmp_path
    write_corpus(repo_root, {VAR_PATH: var_text('secret')})

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    assert any(
        f["rule_id"] == "R-LINT-013" and f["severity"] == "fail"
        for f in doc["findings"]
    )


def test_non_secret_var_with_default_has_no_r_lint_013(tmp_path):
    repo_root = tmp_path
    write_corpus(repo_root, {VAR_PATH: var_text('non-secret')})

    report = spec_linter.lint(None, repo_root)

    assert lint_013_fails(report) == []