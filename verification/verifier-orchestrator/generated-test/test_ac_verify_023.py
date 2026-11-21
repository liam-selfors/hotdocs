# hotdocs-criterion: sha256:edb6c94457e38638e188b270075d009099672d4c79847cc61a48d411b2e2f619
import hashlib
import json
from pathlib import Path

import pytest

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"
TEST_FILENAME = "test_ac_widget_001.py"

BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": REQUIREMENT_ID,
    "criterion_text": "Given a widget is 1\nWhen make is invoked with 1\nThen result equals 1",
    "requirement_text": "R-WIDGET-001 make MUST return its argument.",
    "interface": "# Library\n\nmake(x: int) -> int",
    "glossary": "# Glossary\n\n- **Widget** - a thing.",
    "dependency_interfaces": {},
    "testing": "",
}

HASH_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")

PASSING_BODY = "def test_ok():\n    assert True\n"
FAILING_BODY = "def test_bad():\n    assert False\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def correct_header():
    payload = json.dumps(
        {k: BUNDLE[k] for k in HASH_KEYS},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, cached_content, probe_ok, probe_findings):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
        "---\n\n"
        "# Widget\n\n"
        "## Purpose\n\nMakes widgets.\n\n"
        "## Scope\n\n- In scope: make.\n\n"
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
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n\n**" + REQUIREMENT_ID + "** - `make` MUST return its argument.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget is 1\n"
        "When make is invoked with 1\n"
        "Then result equals 1\n"
        "```\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\nmake(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n\n"
        "# Widget capability\n\n## Purpose\n\nWidgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** - a thing.\n")

    # The component's own code: empty module, tests import nothing from it.
    write(repo_root / "gen" / SLUG / "widget.py", "")

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    # test-probe stand-in.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "OK = " + repr(probe_ok) + "\n"
        "FINDINGS = " + repr(probe_findings) + "\n\n"
        "class ProbeReport:\n"
        "    def __init__(self, ok, findings, tests_run, tests_reached):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = tests_run\n"
        "        self.tests_reached = tests_reached\n\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': [dict(f) for f in self.findings],\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport(OK, [dict(f) for f in FINDINGS], 0, 0)\n",
    )

    if cached_content is not None:
        write(
            repo_root / "verification" / SLUG / "generated-test" / TEST_FILENAME,
            cached_content,
        )


def make_test_author(log_path, content):
    def test_author_stand_in(bundle):
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

    return test_author_stand_in


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
    [None, "# hotdocs-criterion: sha256:" + "0" * 64],
    ids=["no-header", "zero-hash-header"],
)
def test_stale_cached_test_is_authored_again(tmp_path, stale_first_line):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    if stale_first_line is None:
        cached = FAILING_BODY
    else:
        cached = stale_first_line + "\n" + FAILING_BODY
    build_fixture(repo_root, cached, True, [])
    log_path = tmp_path / "author_calls.log"
    author = make_test_author(log_path, correct_header() + "\n" + PASSING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    assert call_count(log_path) == 1
    c = criterion_result(report)
    assert field(c, "result") == "pass", c


def test_current_cached_test_is_reused(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, correct_header() + "\n" + PASSING_BODY, True, [])
    log_path = tmp_path / "author_calls.log"
    author = make_test_author(log_path, correct_header() + "\n" + PASSING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    assert call_count(log_path) == 0
    c = criterion_result(report)
    assert field(c, "result") == "pass", c


def test_probe_failure_reauthors_once_then_fails_as_test(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    findings = [
        {
            "kind": "undefined_name",
            "severity": "error",
            "line": 2,
            "message": "undefined name 'tmp_dir'",
        }
    ]
    build_fixture(repo_root, correct_header() + "\n" + PASSING_BODY, False, findings)
    log_path = tmp_path / "author_calls.log"
    author = make_test_author(log_path, correct_header() + "\n" + PASSING_BODY)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    assert call_count(log_path) == 1
    c = criterion_result(report)
    assert field(c, "result") == "fail", c
    assert field(c, "failure_origin") == "test", c
    detail = field(c, "failure_detail")
    assert field(detail, "message") == "test failed its probe: undefined_name", c


def test_current_test_failing_against_code_is_implementation_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, correct_header() + "\n" + FAILING_BODY, True, [])

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    c = criterion_result(report)
    assert field(c, "result") == "fail", c
    assert field(c, "failure_origin") == "implementation", c