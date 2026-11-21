# hotdocs-criterion: sha256:5006e4ae54d8e9c70eb18b3c26b5c5796ed1dc0fa814857ae91bb444d10b74ca
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget-thing"
SLUG = "widget-thing"
MODULE = "widget_thing"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def expected_bundle(nonce):
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "criterion text " + nonce,
        "requirement_text": "requirement text " + nonce,
        "interface": "interface text " + nonce,
        "glossary": "glossary text " + nonce,
        "dependency_interfaces": {},
        "testing": "testing text " + nonce,
    }


def build_fixture(repo_root, nonce):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget Thing\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
        "---\n\n"
        "# Widget Thing\n\n"
        "## Purpose\n\nCounts widgets.\n\n"
        "## Scope\n\n- In scope: counting.\n\n"
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
        "# " + REQUIREMENT_ID + "\n\n"
        "**" + REQUIREMENT_ID + "** — `widget_count` MUST return its argument.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a widget count of 3\n"
        "When widget_count is called with it\n"
        "Then the result is 3\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nwidget_count(n: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n\n"
        "# Widgets\n\n## Purpose\n\nWidgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # The component's own code: no mutation sites.
    write(
        repo_root / "gen" / SLUG / (MODULE + ".py"),
        "def widget_count(n):\n    return n\n",
    )

    # spec-bundle-assembler stand-in.
    assembler_log = repo_root / "assembler_calls.log"
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "import json\n"
        "\n"
        "LOG = " + repr(str(assembler_log)) + "\n"
        "BUNDLE = json.loads(" + repr(json.dumps(expected_bundle(nonce))) + ")\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps([component_id, criterion_id, str(repo_root)]) + '\\n')\n"
        "    return dict(BUNDLE, dependency_interfaces=dict(BUNDLE['dependency_interfaces']))\n",
    )

    # test-probe stand-in: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )
    return assembler_log


def authored_source(marker, passing):
    return (
        "def test_authored_by_mock():\n"
        "    with open(" + repr(str(marker)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('ran\\n')\n"
        "    assert " + ("True" if passing else "False") + "\n"
    )


def make_author(calls, source):
    def test_author(bundle):
        calls.append(bundle)
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "mock-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/test_ac_widget_001.py",
                "content": source,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def run_case(tmp_path, passing):
    repo_root = tmp_path / ("repo_pass" if passing else "repo_fail")
    repo_root.mkdir()
    nonce = "nonce-" + ("p" if passing else "f") + "-7731"
    assembler_log = build_fixture(repo_root, nonce)
    cached = repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py"
    assert not cached.exists()

    marker = tmp_path / ("marker_pass.log" if passing else "marker_fail.log")
    calls = []
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_author(calls, authored_source(marker, passing))
    )
    return repo_root, nonce, assembler_log, marker, calls, report


def criterion_entry(report):
    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(entries) == 1, criteria
    return entries[0]


def check_author_bundle(calls, nonce):
    assert len(calls) == 1, calls
    received = calls[0]
    expected = expected_bundle(nonce)
    for key, value in expected.items():
        assert field(received, key) == value, key


def check_assembler_calls(assembler_log, repo_root):
    assert assembler_log.is_file()
    lines = [json.loads(line) for line in assembler_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    matching = [entry for entry in lines if entry[0] == COMPONENT_ID and entry[1] == CRITERION_ID]
    assert matching, lines
    for entry in matching:
        assert Path(entry[2]).resolve() == repo_root.resolve()


def test_test_author_gets_assembled_bundle_and_passing_code_is_run(tmp_path):
    repo_root, nonce, assembler_log, marker, calls, report = run_case(tmp_path, passing=True)

    check_assembler_calls(assembler_log, repo_root)
    check_author_bundle(calls, nonce)

    entry = criterion_entry(report)
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == "pass"
    authoring = field(entry, "test_authoring")
    assert field(authoring, "model") == "mock-model"
    assert field(authoring, "cache_hit") is False

    # The returned code was actually executed.
    assert marker.is_file()
    assert "ran" in marker.read_text(encoding="utf-8")


def test_returned_failing_code_produces_fail_result(tmp_path):
    repo_root, nonce, assembler_log, marker, calls, report = run_case(tmp_path, passing=False)

    check_assembler_calls(assembler_log, repo_root)
    check_author_bundle(calls, nonce)

    entry = criterion_entry(report)
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "implementation"

    # The returned code was actually executed.
    assert marker.is_file()
    assert "ran" in marker.read_text(encoding="utf-8")