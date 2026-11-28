# hotdocs-criterion: sha256:ac3486f591e6d28911df060a22958029275d9ef8fc9038a6998d503f18ea7a9c
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


COMPONENT_MD = 'specs/components/foo/component.md'


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_dict(value):
    if isinstance(value, (str, bytes)):
        return json.loads(value)
    return value


def changes():
    glossary = (
        '# Glossary\n'
        '\n'
        '- **Foo** — a made thing.\n'
    )
    old = 'No deltas from `specs/glossary.md`.\n'
    original = CLEAN_CORPUS[COMPONENT_MD]
    assert old in original
    component = original.replace(
        old, '- **Foo** — a widget the team sells by weight.\n'
    )
    cli = (
        '# CLI\n'
        '\n'
        '```\n'
        'foo [--x]\n'
        '```\n'
    )
    return {
        'specs/glossary.md': glossary,
        COMPONENT_MD: component,
        'specs/components/foo/interface/cli.md': cli,
    }


def build(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_corpus(repo_root, changes())
    return repo_root


def sev(finding):
    return str(field(finding, "severity"))


def lint015(report):
    return [f for f in field(report, "findings")
            if field(f, "rule_id") == "R-LINT-015"]


def json_lint015(report):
    data = as_dict(report.to_json())
    return [f for f in data["findings"] if f["rule_id"] == "R-LINT-015"]


def test_no_judge_reports_skipped_and_counts(tmp_path):
    repo_root = build(tmp_path)
    report = spec_linter.lint(None, repo_root)

    found = lint015(report)
    assert len(found) == 1, found
    assert sev(found[0]) == "skipped"
    assert "component.md" in str(field(found[0], "file"))

    findings = field(report, "findings")
    n_fail = sum(1 for f in findings if sev(f) == "fail")
    n_warn = sum(1 for f in findings if sev(f) == "warn")
    n_skip = sum(1 for f in findings if sev(f) == "skipped")
    assert n_warn >= 1
    assert n_skip >= 1

    assert field(report, "hard_failures") == n_fail
    assert field(report, "warnings") == n_warn
    assert field(report, "skipped") == n_skip

    data = as_dict(report.to_json())
    summary = data["summary"]
    assert summary["hard_failures"] == n_fail
    assert summary["warnings"] == n_warn
    assert summary["skipped"] == n_skip


def test_strict_counts_warns_as_failures(tmp_path):
    repo_root = build(tmp_path)
    report = spec_linter.lint(None, repo_root, strict=True)
    findings = field(report, "findings")
    n_warn = sum(1 for f in findings if sev(f) == "warn")
    assert n_warn >= 1
    assert field(report, "hard_failures") == n_warn


def test_judge_conflict_is_fail_with_rationale(tmp_path):
    repo_root = build(tmp_path)

    def judge(term, local_text, glossary_text):
        return (True, "contradicts the glossary")

    report = spec_linter.lint(None, repo_root, judge=judge)
    found = lint015(report)
    assert len(found) == 1, found
    assert sev(found[0]) == "fail"

    jfound = json_lint015(report)
    assert len(jfound) == 1
    assert jfound[0]["severity"] == "fail"
    assert jfound[0]["rationale"] == "contradicts the glossary"


def test_judge_consistent_reports_nothing(tmp_path):
    repo_root = build(tmp_path)

    def judge(term, local_text, glossary_text):
        return (False, "consistent")

    report = spec_linter.lint(None, repo_root, judge=judge)
    assert lint015(report) == []
    assert json_lint015(report) == []


def test_judge_none_is_skipped_without_rationale(tmp_path):
    repo_root = build(tmp_path)

    def judge(term, local_text, glossary_text):
        return None

    report = spec_linter.lint(None, repo_root, judge=judge)
    found = lint015(report)
    assert len(found) == 1, found
    assert sev(found[0]) == "skipped"

    jfound = json_lint015(report)
    assert len(jfound) == 1
    assert jfound[0]["severity"] == "skipped"
    assert "rationale" not in jfound[0]