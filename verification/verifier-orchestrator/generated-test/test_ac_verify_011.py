# hotdocs-criterion: sha256:793b6ba2afc759e44c1ceb3be8eac721c5296d2f9140257d3654bff3d53aa5b3
import json
import re
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERIA = [
    ("AC-FOO-001", "R-FOO-001", "generated-test"),
    ("AC-FOO-002", "R-FOO-001", "generated-test"),
    ("AC-FOO-003", "R-FOO-002", "generated-test"),
    ("AC-FOO-004", "R-FOO-003", "llm-judge"),
]

GHERKIN = {
    "AC-FOO-001": "Given a widget is 1\nWhen bar_value is invoked with 1\nThen result equals 1",
    "AC-FOO-002": "Given a widget is 2\nWhen bar_value is invoked with 2\nThen result equals 2",
    "AC-FOO-003": "Given a widget is 3\nWhen bar_value is invoked with 3\nThen result equals 3",
    "AC-FOO-004": "Given the spec is clear\nWhen a reader reads it\nThen it has no contradiction",
}

PASSING_TEST = "def test_ok():\n    assert 1 == 1\n"
FAILING_TEST = "def test_bad():\n    expected = 5\n    actual = 3\n    assert expected == actual\n"

INTERFACE_TEXT = "# Library\n\n```\nbar_value(x: int) -> int\n```\n"


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "realizes: [P-FOO]\n"
        "---\n\n"
        "# Foo\n\n"
        "## Purpose\n\nA fixture component.\n\n"
        "## Scope\n\n- In scope: fixtures.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    for rid in ("R-FOO-001", "R-FOO-002", "R-FOO-003"):
        write(
            comp / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** - The component MUST behave.\n",
        )
    for cid, covers, kind in CRITERIA:
        write(
            comp / "acceptance" / (cid + ".md"),
            "# " + cid + "\n\n"
            "Covers: " + covers + "\n"
            "Kind: " + kind + "\n\n"
            "```gherkin\n" + GHERKIN[cid] + "\n```\n",
        )
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "---\n\n"
        "# Foo capability\n\n## Purpose\n\nFixture.\n\n## Scope\n\n- Fixture.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    write(repo_root / "gen" / "foo" / "foo.py", "")

    bundles = {}
    for cid, covers, kind in CRITERIA:
        bundles[cid] = {
            "component_id": "comp-foo",
            "criterion_id": cid,
            "covers": covers,
            "criterion_text": GHERKIN[cid],
            "requirement_text": "**" + covers + "** - The component MUST behave.",
            "interface": INTERFACE_TEXT,
            "glossary": "# Glossary",
            "dependency_interfaces": {},
            "testing": "",
        }
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLES = " + repr(bundles) + "\n\n\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLES[criterion_id])\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n\n\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n\n\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )


def make_test_author(log_path):
    def test_author_stand_in(bundle):
        cid = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(cid) + "\n")
        content = FAILING_TEST if cid == "AC-FOO-003" else PASSING_TEST
        name = "test_" + str(cid).lower().replace("-", "_") + ".py"
        return {
            "component_id": "comp-foo",
            "criterion_id": cid,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {"path": "verification/foo/generated-test/" + name, "content": content},
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author_stand_in


def check_projection(rr):
    assert isinstance(rr, dict)
    assert rr == {"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"}
    for key, value in rr.items():
        assert isinstance(key, str) and re.fullmatch(r"R-[A-Z0-9]+-\d{3}", key)
        assert value in ("pass", "fail")
    dumped = json.dumps(rr)
    for forbidden in (
        "Given", "When", "Then", "gherkin", "rationale",
        "expected", "actual", "failure_detail", "message", "AC-FOO",
    ):
        assert forbidden not in dumped
    for gherkin in GHERKIN.values():
        for line in gherkin.splitlines():
            assert line not in dumped


def test_requirement_results_projection(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-foo", repo_root, judge=None, test_author=make_test_author(log_path)
    )

    criteria = field(report, "criteria")
    results = {field(c, "id"): field(c, "result") for c in criteria}
    assert results["AC-FOO-001"] == "pass"
    assert results["AC-FOO-002"] == "pass"
    assert results["AC-FOO-003"] == "fail"
    assert results["AC-FOO-004"] == "skipped"

    check_projection(field(report, "requirement_results"))
    check_projection(report.to_dict()["requirement_results"])