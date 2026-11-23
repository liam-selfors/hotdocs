# hotdocs-criterion: sha256:f618c990e1ff66b2c825d0a2f5d257b9281dcc66fbdc9e236aed5377eeae63b0
import hashlib
import json
from pathlib import Path

import pytest

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
MODULE = "widget"
CRITERION_ID = "AC-WIDGET-001"
TEST_FILENAME = "test_ac_widget_001.py"

BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": "R-WIDGET-001",
    "criterion_text": "Given a widget\nWhen make_widget is invoked\nThen it returns a widget",
    "requirement_text": "R-WIDGET-001: make_widget MUST return its argument.",
    "interface": "# Library\n\nmake_widget(x: int) -> int",
    "glossary": "# Glossary\n\n- **Widget** - a thing.",
    "dependency_interfaces": {},
    "testing": "",
}

PASSING_BODY = "\n\ndef test_widget_passes():\n    assert 1 + 1 == 2\n"
FAILING_BODY = "\n\ndef test_widget_fails():\n    assert 1 + 1 == 3\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def header_line():
    payload = json.dumps(
        {k: BUNDLE[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, cached_content, probe_ok, probe_findings):
    fence = "```"
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n\n"
        "# Widget\n\n"
        "## Purpose\n\nMakes widgets.\n\n"
        "## Scope\n\n- In scope: widgets.\n\n"
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
        "# R-WIDGET-001\n\n**R-WIDGET-001** - make_widget MUST return its argument.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n" + fence + "\nmake_widget(x: int) -> int\n" + fence + "\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n\n"
        + fence + "gherkin\n"
        "Given a widget\n"
        "When make_widget is invoked\n"
        "Then it returns a widget\n"
        + fence + "\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "widgets.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n\n"
        "# Widgets\n\n"
        "## Purpose\n\nWidgets.\n\n"
        "## Scope\n\n- Widgets.\n\n"
        "### CS-WIDGET-001\n\n"
        "Covers: P-WIDGET\n\n"
        + fence + "gherkin\n"
        "Given a widget\n"
        "When it is made\n"
        "Then it exists\n"
        + fence + "\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** - a thing.\n")

    write(repo_root / "gen" / SLUG / (MODULE + ".py"), "")

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "OK = " + repr(probe_ok) + "\n"
        "FINDINGS = " + repr(probe_findings) + "\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self, ok, findings, tests_run, tests_reached):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = tests_run\n"
        "        self.tests_reached = tests_reached\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': [dict(f) for f in self.findings],\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    findings = [dict(f) for f in FINDINGS]\n"
        "    if OK:\n"
        "        return ProbeReport(True, findings, 1, 1)\n"
        "    return ProbeReport(False, findings, 0, 0)\n",
    )

    if cached_content is not None:
        write(
            repo_root / "verification" / SLUG / "generated-test" / TEST_FILENAME,
            cached_content,
        )


def make_author(log_path, content):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "stand-in-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/" + TEST_FILENAME,
                "content": content,
            },
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author


def call_count(log_path):
    if not log_path.exists():
        return 0
    return len([line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()])


def find_criterion(report):
    for entry in field(report, "criteria"):
        if field(entry, "id") == CRITERION_ID:
            return entry
    raise AssertionError("criterion " + CRITERION_ID + " missing from report")


@pytest.mark.parametrize(
    "stale_first_line",
    [None, "# hotdocs-criterion: sha256:" + "0" * 64],
    ids=["no-header", "zero-header"],
)
def test_stale_cached_test_is_authored_again(tmp_path, stale_first_line):
    repo_root = tmp_path / "repo"
    if stale_first_line is None:
        cached = PASSING_BODY.lstrip("\n")
    else:
        cached = stale_first_line + PASSING_BODY
    build_fixture(repo_root, cached, True, [])
    log_path = tmp_path / "author_calls.log"
    author = make_author(log_path, header_line() + PASSING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    assert call_count(log_path) == 1
    assert field(find_criterion(report), "result") == "pass"


def test_current_cached_test_is_reused(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, header_line() + PASSING_BODY, True, [])
    log_path = tmp_path / "author_calls.log"
    author = make_author(log_path, header_line() + PASSING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    assert call_count(log_path) == 0
    assert field(find_criterion(report), "result") == "pass"


def test_probe_failing_test_is_authored_once_then_fails_as_test(tmp_path):
    repo_root = tmp_path / "repo"
    findings = [
        {"kind": "undefined_name", "severity": "error", "line": 3,
         "message": "undefined name 'tmp_dir'"},
    ]
    build_fixture(repo_root, header_line() + PASSING_BODY, False, findings)
    log_path = tmp_path / "author_calls.log"
    author = make_author(log_path, header_line() + PASSING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    assert call_count(log_path) == 1
    entry = find_criterion(report)
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"
    detail = field(entry, "failure_detail")
    assert field(detail, "message") == "test failed its probe: undefined_name"


def test_current_test_failing_against_code_is_implementation_failure(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, header_line() + FAILING_BODY, True, [])

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    entry = find_criterion(report)
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "implementation"