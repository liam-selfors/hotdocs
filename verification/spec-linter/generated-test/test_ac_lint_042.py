# hotdocs-criterion: sha256:2ac3f4ebac38fbe1205fb5f840c8d120f599bb8bb4a8fd1c66864fd7dd6bfc15
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_linter


def _load_spec_linter():
    gen = next(p for p in Path(spec_linter.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_REL = "specs/components/foo/component.md"


def _frontmatter_lines(drivers_line):
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "sealed: true",
        "source_path: legacy/foo/",
    ]
    if drivers_line is not None:
        lines.append(drivers_line)
    lines.append("---")
    return lines


BODY_LINES = [
    "",
    "# Foo",
    "",
    "## Purpose",
    "",
    "Foo does one small thing for its callers.",
    "",
    "## Scope",
    "",
    "- In scope: the one small thing.",
    "- Out of scope: everything else.",
    "",
    "## Definitions",
    "",
    "None.",
    "",
    "## Behavior",
    "",
    "See `requirements/`.",
    "",
    "## Interfaces",
    "",
    "See `interface/`.",
    "",
    "## Data",
    "",
    "See `interface/data/`.",
    "",
    "## Acceptance criteria",
    "",
    "See `acceptance/`.",
    "",
    "## Non-functional constraints",
    "",
    "See `constraints.md`.",
    "",
    "## Open questions",
    "",
    "## Change log",
    "",
    "- Initial draft.",
    "",
]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, drivers_line):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a small thing foo handles.\n",
    )
    comp = specs / "components" / "foo"
    fm = _frontmatter_lines(drivers_line)
    _write(comp / "component.md", "\n".join(fm + BODY_LINES))
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST return the widget it is given.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "Given a widget\n"
        "When foo is called with it\n"
        "Then foo returns the same widget\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(widget: str) -> str\n```\n\nReturns `widget` unchanged.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n"
        "- Latency: foo returns within 10 ms; measured by timing 100 calls in a test.\n",
    )
    drivers_index = None
    if drivers_line is not None:
        drivers_index = fm.index(drivers_line) + 1
    return drivers_index


def _driver_definition(repo_root):
    _write(
        repo_root / "specs" / "architecture" / "test-driver-mine.md",
        "---\n"
        "id: arch-test-driver-mine\n"
        "title: Test Driver mine\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n\n"
        "# Test Driver mine\n\n"
        "## Purpose\n\n"
        "A test driver defined in this repository.\n",
    )


def _findings_on_line(report, line):
    out = []
    for f in field(report, "findings"):
        if field(f, "file") == COMPONENT_REL and field(f, "line") == line:
            out.append(f)
    return out


def test_baseline_corpus_is_lint_clean(tmp_path):
    linter = _load_spec_linter()
    _build_corpus(tmp_path, None)
    report = linter.lint(None, tmp_path)
    assert field(report, "hard_failures") == 0, [
        (field(f, "rule_id"), field(f, "file"), field(f, "line"), field(f, "message"))
        for f in field(report, "findings")
    ]


@pytest.mark.parametrize(
    "item, with_definition, expected",
    [
        ("Bad_Name", False, "driver 'Bad_Name' is not a driver name"),
        ("nodrv", False, "test driver 'nodrv' has no definition or adapter"),
        (
            "mine",
            True,
            "test driver 'mine' is defined in this repository; depends_on must list comp-driver-mine",
        ),
    ],
)
def test_bad_drivers_item_reports_one_fail_on_drivers_line(tmp_path, item, with_definition, expected):
    linter = _load_spec_linter()

    baseline_root = tmp_path / "baseline"
    _build_corpus(baseline_root, None)
    assert linter.lint(None, baseline_root).hard_failures == 0

    repo_root = tmp_path / "repo"
    drivers_line = "drivers: [" + item + "]"
    line = _build_corpus(repo_root, drivers_line)
    if with_definition:
        _driver_definition(repo_root)

    report = linter.lint(None, repo_root)
    on_line = _findings_on_line(report, line)
    fails = [f for f in on_line if field(f, "severity") == "fail"]
    assert len(fails) == 1, [
        (field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in on_line
    ]
    assert field(fails[0], "message") == expected


def test_driver_with_planted_adapter_has_no_finding(tmp_path):
    linter = _load_spec_linter()

    baseline_root = tmp_path / "baseline"
    _build_corpus(baseline_root, None)
    assert linter.lint(None, baseline_root).hard_failures == 0

    repo_root = tmp_path / "repo"
    line = _build_corpus(repo_root, "drivers: [fake]")
    _write(
        repo_root / "gen" / "driver-fake" / "driver_fake.py",
        "NAME = " + repr("fake") + "\n",
    )
    assert not (repo_root / "specs" / "architecture" / "test-driver-fake.md").exists()

    report = linter.lint(None, repo_root)
    on_line = _findings_on_line(report, line)
    assert on_line == [], [
        (field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in on_line
    ]