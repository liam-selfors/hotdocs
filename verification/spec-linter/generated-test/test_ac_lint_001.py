# hotdocs-criterion: sha256:4945e2e3666863f7d6c29bc05385a756cd71122b15d80f9d6a7739943e92e27e
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


COMPONENT_PATH = 'specs/components/foo/component.md'


def _no_owners_changes():
    original = CLEAN_CORPUS[COMPONENT_PATH]
    assert 'owners: [team-a]\n' in original
    return {COMPONENT_PATH: original.replace('owners: [team-a]\n', '', 1)}


def _r001_fail_findings(findings):
    out = []
    for f in findings:
        if field(f, "rule_id") == "R-LINT-001" and field(f, "severity") == "fail":
            out.append(f)
    return out


def _norm(path_value):
    return str(path_value).replace("\\", "/")


def test_clean_corpus_has_no_r_lint_001_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_corpus(repo_root)
    report = spec_linter.lint(None, repo_root)
    assert _r001_fail_findings(field(report, "findings")) == []
    assert field(report, "hard_failures") == 0


def test_missing_owners_in_component_md_gives_fail_r_lint_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_corpus(repo_root, _no_owners_changes())

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    hits = _r001_fail_findings(findings)
    assert hits, "expected a fail-severity R-LINT-001 finding, got: " + repr(findings)
    assert any(_norm(field(f, "file")).endswith(COMPONENT_PATH) for f in hits)
    assert field(report, "hard_failures") >= 1


def test_missing_owners_cli_json_report(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_corpus(repo_root, _no_owners_changes())

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [
        f for f in doc["findings"]
        if f["rule_id"] == "R-LINT-001" and f["severity"] == "fail"
    ]
    assert hits
    assert any(_norm(f["file"]).endswith(COMPONENT_PATH) for f in hits)
    assert doc["summary"]["hard_failures"] >= 1