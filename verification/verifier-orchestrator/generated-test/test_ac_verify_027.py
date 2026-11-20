# hotdocs-criterion: sha256:45ebeb6ac24e6a976188edaad833d751ff1de83441bde34dd19b5fab5c63e7a0
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


COVERS = {"AC-QUX-001": "R-QUX-001", "AC-QUX-002": "R-QUX-002"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def bundle_value(bundle, name):
    if isinstance(bundle, dict):
        return bundle[name]
    try:
        return bundle[name]
    except Exception:
        return getattr(bundle, name)


def bundle_for(criterion_id):
    covers = COVERS[criterion_id]
    return {
        "component_id": "comp-qux",
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": "criterion text for " + criterion_id,
        "requirement_text": "requirement text for " + covers,
        "interface": "qux() -> int",
        "glossary": "glossary text",
        "dependency_interfaces": {},
        "testing": "",
    }


def header_for(bundle):
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: bundle_value(bundle, k) for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


FIRST_BODY = (
    "import qux\n"
    "\n"
    "\n"
    "def test_qux_returns_four():\n"
    "    assert qux.qux() == 4\n"
)

SECOND_BODY = (
    "from pathlib import Path\n"
    "\n"
    "import qux\n"
    "\n"
    "\n"
    "def test_qux_returns_four_in_repo():\n"
    "    assert qux.qux() == 4\n"
    "    assert (Path.cwd() / \"specs\").is_dir()\n"
)


ASSEMBLER_SOURCE = (
    "COVERS = {'AC-QUX-001': 'R-QUX-001', 'AC-QUX-002': 'R-QUX-002'}\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    covers = COVERS[criterion_id]\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': covers,\n"
    "        'criterion_text': 'criterion text for ' + criterion_id,\n"
    "        'requirement_text': 'requirement text for ' + covers,\n"
    "        'interface': 'qux() -> int',\n"
    "        'glossary': 'glossary text',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)


def probe_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport()\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Qux** — a fixture term.\n")
    write(
        repo_root / "specs" / "product" / "P-QUX.md",
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
        "Provides qux.\n",
    )
    comp = repo_root / "specs" / "components" / "qux"
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
    write(comp / "requirements" / "R-QUX-001.md", "**R-QUX-001** — `qux()` MUST return 4.\n")
    write(comp / "requirements" / "R-QUX-002.md", "**R-QUX-002** — `qux()` MUST return 4 in the repo.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nqux() -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    for cid in ("AC-QUX-001", "AC-QUX-002"):
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
    write(repo_root / "gen" / "qux" / "qux.py", "def qux():\n    return 2 * 2\n")
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_SOURCE)
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source(repo_root / "probe.log"))

    gt = repo_root / "verification" / "qux" / "generated-test"
    first = gt / "test_ac_qux_001.py"
    second = gt / "test_ac_qux_002.py"
    write(first, header_for(bundle_for("AC-QUX-001")) + "\n" + FIRST_BODY)
    write(second, header_for(bundle_for("AC-QUX-002")) + "\n" + SECOND_BODY)
    return first, second


def test_ac_verify_027(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    first, second = build_fixture(repo_root)
    author_log = repo_root / "author.log"

    def test_author(bundle):
        with open(author_log, "a") as fh:
            fh.write(str(bundle_value(bundle, "criterion_id")) + "\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "ignored.py", "content": header_for(bundle) + "\n" + FIRST_BODY},
        }

    report = verifier_orchestrator.verify("comp-qux", repo_root, test_author=test_author)

    criteria = {field(c, "id"): c for c in field(report, "criteria")}
    c1 = criteria["AC-QUX-001"]
    c2 = criteria["AC-QUX-002"]

    assert field(c1, "result") == "pass"

    assert field(c2, "result") == "fail"
    assert field(c2, "failure_origin") == "test"
    assert field(field(c2, "failure_detail"), "message") == "test fails in the mutation sandbox"
    assert not second.exists()

    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") is not None