# hotdocs-criterion: sha256:f5793b3756a1529331c0ecf8e56e716529eac20ec77b7597ed209dbd3fecedf7
import hashlib
import json
import sys
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-qux"
SLUG = "qux"
MODULE = "qux"
CRITERIA = ["AC-QUX-001", "AC-QUX-002"]
COVERS = {"AC-QUX-001": "R-QUX-001", "AC-QUX-002": "R-QUX-002"}

INTERFACE_TEXT = "# Library\n\n```\nqux() -> int\n```\n"
GLOSSARY_TEXT = "Glossary text for qux."
TESTING_TEXT = ""


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def bundle_for(criterion_id):
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": criterion_id,
        "covers": COVERS[criterion_id],
        "criterion_text": "Criterion text for " + criterion_id,
        "requirement_text": "Requirement text for " + COVERS[criterion_id],
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": TESTING_TEXT,
    }


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def criterion_body(criterion_id):
    body = (
        "from pathlib import Path\n"
        "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_qux_value():\n"
        "    assert qux.qux() == 4\n"
    )
    if criterion_id == "AC-QUX-002":
        body += (
            "\n"
            "\n"
            "def test_specs_dir_present():\n"
            "    assert (Path.cwd() / \"specs\").is_dir()\n"
        )
    return body


def criterion_file_content(criterion_id):
    return header_for(bundle_for(criterion_id)) + "\n" + criterion_body(criterion_id)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Qux capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides qux.\n",
    )
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-QUX]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Computes qux.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: qux.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
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
        "- Initial.\n",
    )
    write(comp / "requirements" / "R-QUX-001.md", "**R-QUX-001** — `qux()` MUST return 4.\n")
    write(comp / "requirements" / "R-QUX-002.md", "**R-QUX-002** — `qux()` MUST return 4 from the repo root.\n")
    for cid in CRITERIA:
        write(
            comp / "acceptance" / (cid + ".md"),
            "# " + cid + "\n"
            "\n"
            "Covers: " + COVERS[cid] + "\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given the qux module\n"
            "When qux is called\n"
            "Then it returns 4\n"
            "```\n",
        )
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / SLUG / (MODULE + ".py"), "def qux():\n    return 2 * 2\n")

    bundles = {cid: bundle_for(cid) for cid in CRITERIA}
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLES = " + repr(bundles) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLES[criterion_id])\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return ProbeReport()\n",
    )

    for cid in CRITERIA:
        name = "test_" + cid.lower().replace("-", "_") + ".py"
        write(repo_root / "verification" / SLUG / "generated-test" / name, criterion_file_content(cid))


def make_author(log_path):
    def author(bundle):
        cid = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(cid) + "\n")
        name = "test_" + str(cid).lower().replace("-", "_") + ".py"
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": cid,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {"path": "verification/qux/generated-test/" + name, "content": criterion_file_content(str(cid))},
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author


def test_ac_verify_027_sandbox_dependent_test_fails_as_test(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=None, test_author=make_author(log_path))

    criteria = {c["id"]: c for c in field(report, "criteria")}
    first = criteria["AC-QUX-001"]
    second = criteria["AC-QUX-002"]

    assert first["result"] == "pass"

    assert second["result"] == "fail"
    assert second["failure_origin"] == "test"
    detail = second["failure_detail"]
    assert field(detail, "message") == "test fails in the mutation sandbox"

    second_file = repo_root / "verification" / SLUG / "generated-test" / "test_ac_qux_002.py"
    assert not second_file.exists()

    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") is not None