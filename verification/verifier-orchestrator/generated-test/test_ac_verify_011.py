# hotdocs-criterion: sha256:245a70a836943a4dca487b2adb9620fa606c30452bd553097a5a00776292506e
"""AC-VERIFY-011: requirement_results projects criterion results onto R-ids.

Two criteria cover R-FOO-001 (both pass), one covers R-FOO-002 (fails), and
an llm-judge criterion covers R-FOO-003 and is skipped (no judge configured).
requirement_results must be exactly
{"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"} and hold
nothing but R-id keys and pass/fail values.
"""

import json
import re
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


CRITERIA = [
    # (criterion id, covers, kind, gherkin lines)
    (
        "AC-FOO-001",
        "R-FOO-001",
        "generated-test",
        [
            "Given a widget ledger holding the entries alpha and beta",
            "When the ledger is summed",
            "Then the widget total equals 3",
        ],
    ),
    (
        "AC-FOO-002",
        "R-FOO-001",
        "generated-test",
        [
            "Given a widget ledger holding the entry gamma",
            "When the ledger is counted",
            "Then the widget count equals 1",
        ],
    ),
    (
        "AC-FOO-003",
        "R-FOO-002",
        "generated-test",
        [
            "Given a widget ledger holding no entries",
            "When the ledger is summed",
            "Then the widget total equals 7",
        ],
    ),
    (
        "AC-FOO-004",
        "R-FOO-003",
        "llm-judge",
        [
            "Given the widget specification text",
            "When a reviewer reads it",
            "Then it states its rounding rule unambiguously",
        ],
    ),
]

REQUIREMENTS = {
    "R-FOO-001": "The widget ledger MUST sum its entries.",
    "R-FOO-002": "The widget ledger MUST report a zero total when empty.",
    "R-FOO-003": "The widget specification MUST state its rounding rule.",
}

PASSING_TEST = "def test_passes():\n    assert 1 + 1 == 2\n"
FAILING_TEST = "def test_fails():\n    assert 1 + 1 == 3\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def acceptance_text(criterion_id, covers, kind, lines):
    return (
        "# " + criterion_id + "\n\n"
        "Covers: " + covers + "\n"
        "Kind: " + kind + "\n\n"
        "```gherkin\n" + "\n".join(lines) + "\n```\n"
    )


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
        "---\n\n"
        "# Foo\n\n"
        "## Purpose\n\n"
        "A widget ledger used as a verifier fixture.\n",
    )
    write(
        repo_root / "specs" / "product" / "foo.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n\n"
        "# P-FOO\n\n"
        "A widget ledger capability.\n",
    )
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a fixture term.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nledger_total(entries)\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    for rid, text in REQUIREMENTS.items():
        write(
            comp / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** — " + text + "\n",
        )
    for cid, covers, kind, lines in CRITERIA:
        write(
            comp / "acceptance" / (cid + ".md"),
            acceptance_text(cid, covers, kind, lines),
        )

    # Code under test: an empty module (the tests import nothing from it).
    write(repo_root / "gen" / "foo" / "foo.py", "")

    # spec-bundle-assembler stand-in.
    covers_map = {cid: covers for cid, covers, _k, _l in CRITERIA}
    text_map = {
        cid: "\n".join(lines) for cid, _c, _k, lines in CRITERIA
    }
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "COVERS = " + repr(covers_map) + "\n"
        "TEXTS = " + repr(text_map) + "\n"
        "REQS = " + repr(REQUIREMENTS) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    covers = COVERS.get(criterion_id, '')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': covers,\n"
        "        'criterion_text': TEXTS.get(criterion_id, ''),\n"
        "        'requirement_text': REQS.get(covers, ''),\n"
        "        'interface': 'ledger_total(entries)',\n"
        "        'glossary': 'Widget: a fixture term.',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
    )

    # test-probe stand-in: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return ProbeReport()\n",
    )


def make_test_author(log_path):
    contents = {
        "AC-FOO-001": PASSING_TEST,
        "AC-FOO-002": PASSING_TEST,
        "AC-FOO-003": FAILING_TEST,
    }

    def test_author(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(criterion_id + "\n")
        filename = "test_" + criterion_id.lower().replace("-", "_") + ".py"
        return {
            "component_id": "comp-foo",
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/foo/generated-test/" + filename,
                "content": contents[criterion_id],
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def test_requirement_results_projection(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-foo",
        repo_root,
        judge=None,
        test_author=make_test_author(log_path),
    )

    # Sanity-check the Given: criterion results as the scenario describes.
    by_id = {field(c, "id"): field(c, "result") for c in field(report, "criteria")}
    assert by_id.get("AC-FOO-001") == "pass", by_id
    assert by_id.get("AC-FOO-002") == "pass", by_id
    assert by_id.get("AC-FOO-003") == "fail", by_id
    assert by_id.get("AC-FOO-004") == "skipped", by_id

    called = set(log_path.read_text(encoding="utf-8").split())
    assert called == {"AC-FOO-001", "AC-FOO-002", "AC-FOO-003"}

    expected = {"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"}

    rr = field(report, "requirement_results")
    assert isinstance(rr, dict)
    assert rr == expected

    as_dict = report.to_dict()
    rr_json = as_dict["requirement_results"]
    assert rr_json == expected

    # Only R-id keys and pass/fail string values, nothing nested.
    for mapping in (rr, rr_json):
        for key, value in mapping.items():
            assert isinstance(key, str) and re.fullmatch(r"R-[A-Z0-9]+-[0-9]+", key), key
            assert isinstance(value, str) and value in ("pass", "fail"), value

    # No Gherkin text, rationale or expected/actual values anywhere in it.
    dumped = json.dumps(rr_json, sort_keys=True)
    for forbidden in (
        "Given",
        "When",
        "Then",
        "widget",
        "ledger",
        "rationale",
        "expected",
        "actual",
        "failure_detail",
        "AC-FOO",
    ):
        assert forbidden not in dumped, forbidden
    for _cid, _covers, _kind, lines in CRITERIA:
        for line in lines:
            assert line not in dumped