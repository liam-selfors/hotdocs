# hotdocs-criterion: sha256:0a86de084d8afde3a45af667001ce44b05c18c457dc7087bc022375a1374daef
import json

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_json(value):
    out = value.to_json() if hasattr(value, "to_json") else value
    if isinstance(out, (str, bytes)):
        out = json.loads(out)
    return out


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY_DEF = (
    "a reusable unit of the frobnication pipeline that holds exactly one gizmo."
)
LOCAL_DEF = (
    "within this component, a cached record of one earlier lint run, "
    "stored on disk between invocations."
)


def build_corpus(root):
    specs = root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\n"
        "Canonical vocabulary.\n\n"
        "- **Widget** \u2014 " + GLOSSARY_DEF + "\n",
    )
    write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Foo exists\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n\n"
        "# D1: Foo exists\n\n"
        "## Context\n\nA fixture needs a decision to cite.\n\n"
        "## Decision\n\nFoo exists as a sealed fixture component.\n",
    )
    purpose = (
        "This component exists to exercise the linter fixture paths carefully. "
        * 10
    ).strip()
    write(
        specs / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n"
        "# Foo\n\n"
        "## Purpose\n\n" + purpose + "\n\n"
        "## Rationale\n\nSee D1.\n\n"
        "## Scope\n\n- In scope: fixture behavior.\n- Out of scope: everything else.\n\n"
        "## Definitions\n\n"
        "- **Widget** \u2014 " + LOCAL_DEF + "\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial draft.\n",
    )
    write(
        specs / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n"
        "**R-FOO-001** \u2014 `foo()` MUST return `None` (D1).\n",
    )
    write(
        specs / "components" / "foo" / "interface" / "library.md",
        "# Library\n\n```\nfoo() -> None\n```\n\nReturns nothing.\n",
    )
    write(
        specs / "components" / "foo" / "interface" / "data" / "Thing.md",
        "# `Thing`\n\nA plain marker type with no fields.\n",
    )
    padding = ("This sentence pads the criterion text for size purposes. " * 40).strip()
    write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given the foo module\n"
        "When foo() is called\n"
        "Then it returns None\n"
        "```\n\n" + padding + "\n",
    )
    write(
        specs / "components" / "foo" / "constraints.md",
        "# Constraints\n\n"
        "- `foo()` returns within 10 ms, measured by timing 100 calls.\n",
    )


def by_severity(report, severity):
    return [f for f in field(report, "findings") if field(f, "severity") == severity]


def lint015(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-015"]


def test_ac_lint_034(tmp_path):
    build_corpus(tmp_path)

    # --- no judge ---
    report = spec_linter.lint(None, tmp_path)
    fails = by_severity(report, "fail")
    warns = by_severity(report, "warn")
    skips = by_severity(report, "skipped")
    assert fails == [], [field(f, "message") for f in fails]
    assert len(warns) >= 1

    entries = lint015(report)
    assert len(entries) == 1
    assert field(entries[0], "severity") == "skipped"

    assert field(report, "hard_failures") == len(fails)
    assert field(report, "warnings") == len(warns)
    assert field(report, "skipped") == len(skips)

    summary = as_json(report)["summary"]
    assert summary["hard_failures"] == len(fails)
    assert summary["warnings"] == len(warns)
    assert summary["skipped"] == len(skips)

    # --- strict ---
    strict_report = spec_linter.lint(None, tmp_path, strict=True)
    assert field(strict_report, "hard_failures") == len(warns)

    # --- judge: conflict ---
    calls = []

    def judge_conflict(term, local_text, glossary_text):
        calls.append(term)
        return (True, "contradicts the glossary")

    r1 = spec_linter.lint(None, tmp_path, judge=judge_conflict)
    assert any("widget" in str(t).lower() for t in calls)
    e1 = lint015(r1)
    assert len(e1) == 1
    assert field(e1[0], "severity") == "fail"
    j1 = as_json(e1[0])
    assert j1["rationale"] == "contradicts the glossary"
    assert field(r1, "hard_failures") == len(by_severity(r1, "fail"))

    # --- judge: consistent ---
    def judge_ok(term, local_text, glossary_text):
        return (False, "consistent")

    r2 = spec_linter.lint(None, tmp_path, judge=judge_ok)
    assert lint015(r2) == []

    # --- judge: could not judge ---
    def judge_none(term, local_text, glossary_text):
        return None

    r3 = spec_linter.lint(None, tmp_path, judge=judge_none)
    e3 = lint015(r3)
    assert len(e3) == 1
    assert field(e3[0], "severity") == "skipped"
    j3 = as_json(e3[0])
    assert "rationale" not in j3