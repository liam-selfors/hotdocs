# hotdocs-criterion: sha256:b31a2580a03d9a72f43d3f61969d491bf24c5affa516a20cabe2092677364abe
# Acceptance test for AC-VERIFY-023 (covers R-VERIFY-019).
import hashlib
import json
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
TEST_FILENAME = "test_ac_widget_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": "R-WIDGET-001",
    "criterion_text": "Given a widget\nWhen value is called\nThen it returns 1",
    "requirement_text": "R-WIDGET-001: value() MUST return 1.",
    "interface": "# Library\n\nvalue() -> int\n",
    "glossary": "# Glossary\n",
    "dependency_interfaces": {},
    "testing": "",
}


def correct_header():
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: BUNDLE[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


PASSING_BODY = "\n\ndef test_widget_passes():\n    assert True\n"
FAILING_BODY = (
    "\nimport widget\n\n\n"
    "def test_widget_value_is_two():\n"
    "    assert widget.value() == 2\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, probe_ok, probe_findings, cached_content):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n\n"
        "# Widget\n\n"
        "## Purpose\n\nReturns a fixed value.\n\n"
        "## Scope\n\n- In scope: value().\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "**R-WIDGET-001** — `value()` MUST return 1.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nvalue() -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# AC-WIDGET-001\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget\n"
        "When value is called\n"
        "Then it returns 1\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n\n"
        "# Widget capability\n\n## Purpose\n\nWidgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # Code under test.
    write(repo_root / "gen" / SLUG / "widget.py", "def value():\n    return 1\n")

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n\n\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    # test-probe stand-in.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "OK = " + repr(probe_ok) + "\n"
        "FINDINGS = " + repr(probe_findings) + "\n\n\n"
        "class ProbeReport:\n"
        "    def __init__(self, ok, findings):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': [dict(f) for f in self.findings],\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n\n\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport(OK, [dict(f) for f in FINDINGS])\n",
    )

    if cached_content is not None:
        write(
            repo_root / "verification" / SLUG / "generated-test" / TEST_FILENAME,
            cached_content,
        )


def make_test_author(log_path, content):
    def stand_in(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "stand-in-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/" + TEST_FILENAME,
                "content": content,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return stand_in


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len([ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()])


def criterion_result(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


@pytest.mark.parametrize(
    "stale_first_line",
    [
        None,
        "# hotdocs-criterion: sha256:" + "0" * 64,
    ],
    ids=["no-header", "zero-hash-header"],
)
def test_stale_cached_test_is_authored_again(tmp_path, stale_first_line):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    if stale_first_line is None:
        cached = "import os\n" + PASSING_BODY
    else:
        cached = stale_first_line + "\n" + PASSING_BODY
    build_fixture(repo_root, True, [], cached)
    log_path = tmp_path / "author_calls.log"
    stand_in = make_test_author(log_path, correct_header() + "\n" + PASSING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=stand_in)

    assert call_count(log_path) == 1
    c = criterion_result(report)
    assert field(c, "result") == "pass", c


def test_current_cached_test_is_reused(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, True, [], correct_header() + "\n" + PASSING_BODY)
    log_path = tmp_path / "author_calls.log"
    stand_in = make_test_author(log_path, correct_header() + "\n" + PASSING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=stand_in)

    assert call_count(log_path) == 0
    c = criterion_result(report)
    assert field(c, "result") == "pass", c


def test_probe_failing_test_is_authored_once_then_fails_as_test(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    findings = [
        {
            "kind": "undefined_name",
            "severity": "error",
            "line": 3,
            "message": "undefined name 'tmp_dir'",
        }
    ]
    build_fixture(repo_root, False, findings, correct_header() + "\n" + PASSING_BODY)
    log_path = tmp_path / "author_calls.log"
    stand_in = make_test_author(log_path, correct_header() + "\n" + PASSING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=stand_in)

    assert call_count(log_path) == 1
    c = criterion_result(report)
    assert field(c, "result") == "fail", c
    assert field(c, "failure_origin") == "test", c
    detail = field(c, "failure_detail")
    assert field(detail, "message") == "test failed its probe: undefined_name", c


def test_current_test_failing_against_code_is_implementation_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, True, [], correct_header() + "\n" + FAILING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    c = criterion_result(report)
    assert field(c, "result") == "fail", c
    assert field(c, "failure_origin") == "implementation", c