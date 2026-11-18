# hotdocs-criterion: sha256:0a86de084d8afde3a45af667001ce44b05c18c457dc7087bc022375a1374daef
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sev(value):
    s = field(value, "severity")
    return getattr(s, "value", s)


def as_obj(j):
    if isinstance(j, (str, bytes)):
        return json.loads(j)
    return j


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(root):
    specs = root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this fixture corpus.\n"
        "\n"
        "- **Widget** \u2014 a reusable rendering unit composed of nested frames, "
        "declared once in the layout registry and instantiated by reference.\n",
    )

    comp = specs / "components" / "foo"
    purpose_sentence = (
        "This component turns layout requests into rendered frames for the dashboard. "
    )
    purpose = (purpose_sentence * 9).strip()  # 99 words: above warn 80, below fail 150
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + purpose
        + "\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: rendering frames for layout requests.\n"
        "- Out of scope: persisting layouts.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "- **Widget** \u2014 here, also any clickable toolbar button shown "
        "beside the search box.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n",
    )

    padding_sentence = (
        "Each frame is produced from the request alone and carries no state between calls. "
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 The renderer MUST emit exactly one frame per layout request.\n"
        "\n"
        + (padding_sentence * 20).strip()
        + "\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given one layout request\n"
        "When the renderer runs\n"
        "Then exactly one frame is emitted\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "render(request: dict) -> FooResult\n"
        "```\n"
        "\n"
        "Renders one frame for one layout request.\n",
    )
    write(
        comp / "interface" / "data" / "FooResult.md",
        "# `FooResult`\n"
        "\n"
        "```json\n"
        "{\"frame\": \"string\"}\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Rendering one frame completes within 50 ms, measured by a timing benchmark.\n",
    )


def lint_findings_015(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-015"]


def counts(report):
    findings = field(report, "findings")
    return (
        sum(1 for f in findings if sev(f) == "fail"),
        sum(1 for f in findings if sev(f) == "warn"),
        sum(1 for f in findings if sev(f) == "skipped"),
    )


def assert_summary_consistent(report):
    n_fail, n_warn, n_skip = counts(report)
    assert field(report, "hard_failures") == n_fail
    assert field(report, "warnings") == n_warn
    assert field(report, "skipped") == n_skip
    summary = as_obj(report.to_json())["summary"]
    assert summary["hard_failures"] == n_fail
    assert summary["warnings"] == n_warn
    assert summary["skipped"] == n_skip


def test_ac_lint_034_no_judge_skips_and_counts(tmp_path):
    build_corpus(tmp_path)
    report = spec_linter.lint(None, tmp_path)

    # Preconditions: no fail-severity finding, at least one warn.
    assert field(report, "hard_failures") == 0, [
        (field(f, "rule_id"), field(f, "message")) for f in field(report, "findings")
    ]
    n_fail, n_warn, n_skip = counts(report)
    assert n_fail == 0
    assert n_warn >= 1

    r15 = lint_findings_015(report)
    assert len(r15) == 1
    finding = r15[0]
    assert sev(finding) == "skipped"
    assert str(field(finding, "file")).replace("\\", "/").endswith(
        "specs/components/foo/component.md"
    )
    assert "rationale" not in as_obj(finding.to_json())

    assert n_skip >= 1
    assert_summary_consistent(report)


def test_ac_lint_034_strict_counts_warns_as_failures(tmp_path):
    build_corpus(tmp_path)
    plain = spec_linter.lint(None, tmp_path)
    assert field(plain, "hard_failures") == 0
    _, n_warn, _ = counts(plain)
    assert n_warn >= 1

    strict = spec_linter.lint(None, tmp_path, strict=True)
    assert field(strict, "hard_failures") == n_warn


def test_ac_lint_034_judge_outcomes(tmp_path):
    build_corpus(tmp_path)
    precheck = spec_linter.lint(None, tmp_path)
    assert field(precheck, "hard_failures") == 0

    calls = []

    def make_judge(result):
        def judge(term, local_text, glossary_text):
            calls.append((term, local_text, glossary_text))
            return result
        return judge

    # 1. Conflict -> fail with rationale.
    report = spec_linter.lint(
        None, tmp_path, judge=make_judge((True, "contradicts the glossary"))
    )
    r15 = lint_findings_015(report)
    assert len(r15) == 1
    finding = r15[0]
    assert sev(finding) == "fail"
    fj = as_obj(finding.to_json())
    assert "rationale" in fj
    rationale = fj["rationale"]
    rtext = rationale if isinstance(rationale, str) else json.dumps(rationale)
    assert "contradicts the glossary" in rtext
    assert field(report, "hard_failures") >= 1
    assert_summary_consistent(report)

    assert calls, "judge was never called"
    assert any("widget" in str(c[0]).lower() for c in calls)

    # 2. Consistent -> no R-LINT-015 finding.
    calls.clear()
    report = spec_linter.lint(None, tmp_path, judge=make_judge((False, "consistent")))
    assert lint_findings_015(report) == []
    assert calls
    assert field(report, "hard_failures") == 0
    assert_summary_consistent(report)

    # 3. Judge could not judge -> skipped, no rationale key.
    calls.clear()
    report = spec_linter.lint(None, tmp_path, judge=make_judge(None))
    r15 = lint_findings_015(report)
    assert len(r15) == 1
    finding = r15[0]
    assert sev(finding) == "skipped"
    assert "rationale" not in as_obj(finding.to_json())
    assert calls
    assert field(report, "hard_failures") == 0
    assert_summary_consistent(report)