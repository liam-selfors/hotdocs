# hotdocs-criterion: sha256:4656e7dc5dec30c69cc955d31c7a962af9f8f4a8d835cfbd068d3ac9d2a85742
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SLUG = "qux"
COMPONENT_ID = "comp-qux"
CRITERIA = ("AC-QUX-001", "AC-QUX-002")


def bundle_for(criterion_id):
    covers = "R-QUX-" + criterion_id.split("-")[-1]
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": "criterion text for " + criterion_id,
        "requirement_text": "requirement text for " + covers,
        "interface": "qux() -> int",
        "glossary": "glossary text",
        "dependency_interfaces": {},
        "testing": "",
    }


def header_for(criterion_id):
    bundle = bundle_for(criterion_id)
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def first_test_source():
    return (
        header_for("AC-QUX-001") + "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_qux_returns_four():\n"
        "    assert qux.qux() == 4\n"
    )


def second_test_source():
    return (
        header_for("AC-QUX-002") + "\n"
        "from pathlib import Path\n"
        "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_qux_and_specs_dir():\n"
        "    assert qux.qux() == 4\n"
        "    assert (Path.cwd() / \"specs\").is_dir()\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_path):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-QUX]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Returns four.\n"
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
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Qux capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Qux.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Qux.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Qux** — a thing.\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nqux() -> int\n```\n",
    )
    for criterion_id in CRITERIA:
        num = criterion_id.split("-")[-1]
        write(
            comp / "requirements" / ("R-QUX-" + num + ".md"),
            "**R-QUX-" + num + "** — `qux()` MUST return 4.\n",
        )
        write(
            comp / "acceptance" / (criterion_id + ".md"),
            "# " + criterion_id + "\n"
            "\n"
            "Covers: R-QUX-" + num + "\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given the qux component\n"
            "When qux is called\n"
            "Then it returns 4\n"
            "```\n",
        )

    write(repo_root / "gen" / SLUG / "qux.py", "def qux():\n    return 2 * 2\n")

    bundles = {cid: bundle_for(cid) for cid in CRITERIA}
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLES = " + repr(bundles) + "\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode=\"cold\"):\n"
        "    raise RuntimeError(\"assemble not expected\")\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLES[criterion_id])\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = \"test-probe@1.3.0\"\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\"ok\": self.ok, \"findings\": list(self.findings),\n"
        "                \"tests_run\": self.tests_run, \"tests_reached\": self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )

    gen_tests = repo_root / "verification" / SLUG / "generated-test"
    write(gen_tests / "test_ac_qux_001.py", first_test_source())
    write(gen_tests / "test_ac_qux_002.py", second_test_source())

    sources = {"AC-QUX-001": first_test_source(), "AC-QUX-002": second_test_source()}

    def test_author(bundle):
        criterion_id = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        name = "test_" + criterion_id.lower().replace("-", "_") + ".py"
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {"path": "verification/qux/generated-test/" + name, "content": sources[criterion_id]},
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def test_sandbox_dependent_test_fails_with_test_origin_and_is_deleted(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "author.log"
    test_author = build_fixture(repo_root, log_path)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=test_author)

    criteria = {c["id"]: c for c in field(report, "criteria")}
    first = criteria["AC-QUX-001"]
    second = criteria["AC-QUX-002"]

    assert first["result"] == "pass"

    assert second["result"] == "fail"
    assert second["failure_origin"] == "test"
    assert second["failure_detail"]["message"] == "test fails in the mutation sandbox"
    second_file = repo_root / "verification" / SLUG / "generated-test" / "test_ac_qux_002.py"
    assert not second_file.exists()

    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") is not None