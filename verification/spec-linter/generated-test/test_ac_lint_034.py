# hotdocs-criterion: sha256:beb41619cbf1d208166cf360dcf260500dae40d5e18a2d61ed1f46eda0a78614
import json
from pathlib import Path

import spec_linter


PRODUCT = """---
id: P-FOO
title: Foo works
status: draft
owners: [team-a]
---

# Foo works

## Purpose

A foo can be made.

### CS-FOO-001
Covers: P-FOO
Kind: generated-test

```gherkin
Given nothing
When a foo is made
Then it exists
```
"""

COMPONENT = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
depends_on: []
realizes: [P-FOO]
sealed: false
---

# Foo

## Purpose

Makes a foo.

## Scope

**In scope:** making a foo. **Out of scope:** everything else.

## Definitions

- **Widget** \u2014 here, a blue file kept on the local disk purely for caching purposes.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

None.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
"""

REQUIREMENT = """# R-FOO-001

**R-FOO-001** \u2014 `make_foo()` MUST return the string `"foo"`.
"""

LIBRARY = """# Library

One module file, `foo.py`.

```
make_foo() -> str
```
"""

CLI = """# CLI

```
foo
```
"""

ACCEPTANCE = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given nothing
When make_foo() is called
Then the result is "foo"
```
"""

CONSTRAINTS = """# Foo \u2014 Non-Functional Constraints

- **Pure.** No I/O.
"""

GLOSSARY = """# Glossary

Canonical vocabulary.

- **Widget** \u2014 a reusable unit of frobnication that every component shares
  through its published interface contract.
"""


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_corpus(root):
    write(root, "specs/product/foo.md", PRODUCT)
    write(root, "specs/components/foo/component.md", COMPONENT)
    write(root, "specs/components/foo/requirements/R-FOO-001.md", REQUIREMENT)
    write(root, "specs/components/foo/interface/library.md", LIBRARY)
    write(root, "specs/components/foo/interface/cli.md", CLI)
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md", ACCEPTANCE)
    write(root, "specs/components/foo/constraints.md", CONSTRAINTS)
    write(root, "specs/glossary.md", GLOSSARY)


def as_json(value):
    data = value.to_json()
    if isinstance(data, (str, bytes)):
        data = json.loads(data)
    return data


def sev_count(report, severity):
    return sum(1 for f in field(report, "findings") if field(f, "severity") == severity)


def r015(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-015"]


def r015_json(report):
    data = as_json(report)
    return [f for f in data["findings"] if f["rule_id"] == "R-LINT-015"]


def test_no_judge_skipped_and_counts(tmp_path):
    build_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)

    fails = sev_count(report, "fail")
    warns = sev_count(report, "warn")
    skipped = sev_count(report, "skipped")
    assert fails == 0
    assert warns >= 1

    found = r015(report)
    assert len(found) == 1
    assert field(found[0], "severity") == "skipped"
    assert skipped >= 1

    assert field(report, "hard_failures") == fails
    assert field(report, "warnings") == warns
    assert field(report, "skipped") == skipped

    summary = as_json(report)["summary"]
    assert summary["hard_failures"] == fails
    assert summary["warnings"] == warns
    assert summary["skipped"] == skipped


def test_strict_counts_warns_as_failures(tmp_path):
    build_corpus(tmp_path)
    plain = spec_linter.lint(None, tmp_path)
    warns = sev_count(plain, "warn")
    assert sev_count(plain, "fail") == 0
    assert warns >= 1

    strict = spec_linter.lint(None, tmp_path, strict=True)
    assert field(strict, "hard_failures") == warns


def test_judge_conflict_is_fail_with_rationale(tmp_path):
    build_corpus(tmp_path)
    calls = []

    def judge(term, local_text, glossary_text):
        calls.append((term, local_text, glossary_text))
        return (True, "contradicts the glossary")

    report = spec_linter.lint(None, tmp_path, judge=judge)
    assert calls
    found = r015(report)
    assert len(found) == 1
    assert field(found[0], "severity") == "fail"
    js = r015_json(report)
    assert len(js) == 1
    assert js[0]["severity"] == "fail"
    assert js[0]["rationale"] == "contradicts the glossary"
    if hasattr(found[0], "to_json"):
        fj = as_json(found[0])
        assert fj["rationale"] == "contradicts the glossary"


def test_judge_consistent_gives_no_finding(tmp_path):
    build_corpus(tmp_path)
    calls = []

    def judge(term, local_text, glossary_text):
        calls.append(term)
        return (False, "consistent")

    report = spec_linter.lint(None, tmp_path, judge=judge)
    assert calls
    assert r015(report) == []
    assert r015_json(report) == []


def test_judge_none_is_skipped_without_rationale(tmp_path):
    build_corpus(tmp_path)
    calls = []

    def judge(term, local_text, glossary_text):
        calls.append(term)
        return None

    report = spec_linter.lint(None, tmp_path, judge=judge)
    assert calls
    found = r015(report)
    assert len(found) == 1
    assert field(found[0], "severity") == "skipped"
    js = r015_json(report)
    assert len(js) == 1
    assert js[0]["severity"] == "skipped"
    assert "rationale" not in js[0]
    if hasattr(found[0], "to_json"):
        assert "rationale" not in as_json(found[0])