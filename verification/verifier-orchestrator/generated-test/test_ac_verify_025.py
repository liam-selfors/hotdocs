# hotdocs-criterion: sha256:a2cd07bdd9640cfff633427766b93e786ec7212ecbc3fa18383e1d5ba609ee18
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE_TEXT = {
    "criterion_text": "Given a qux When qux is called Then it returns 4",
    "requirement_text": "R-QUX-001: qux() MUST return twice baz().",
    "interface": "qux() -> int",
    "glossary": "Glossary text.",
    "testing": "",
}


def header_line():
    payload = json.dumps(
        {k: BUNDLE_TEXT[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generated_test_source():
    return (
        header_line() + "\n"
        + "import qux\n"
        + "\n"
        + "\n"
        + "def test_qux_returns_four():\n"
        + "    assert qux.qux() == 4\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_path):
    # Product capability so the unsealed component resolves `realizes`.
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provide qux.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Thing** — a thing.\n")

    comp = repo_root / "specs" / "components" / "qux"
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
        "Returns twice baz.\n"
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
    write(comp / "requirements" / "R-QUX-001.md", "# R-QUX-001\n\n**R-QUX-001** — `qux()` MUST return twice `baz()`.\n")
    write(comp / "interface" / "library.md", "# Library\n\n```\nqux() -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a qux module\n"
        "When qux is called\n"
        "Then it returns 4\n"
        "```\n",
    )

    # Component code: qux loads baz by path from its own __file__.
    write(
        repo_root / "gen" / "qux" / "qux.py",
        "import importlib.util\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def _load_baz():\n"
        "    path = Path(__file__).resolve().parents[1] / \"baz\" / \"baz.py\"\n"
        "    spec = importlib.util.spec_from_file_location(\"baz\", path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n"
        "    return module\n"
        "\n"
        "\n"
        "def qux():\n"
        "    return 2 * _load_baz().baz()\n",
    )
    write(
        repo_root / "gen" / "baz" / "baz.py",
        "def baz():\n"
        "    return 2\n",
    )

    # spec-bundle-assembler stand-in.
    bundle = dict(BUNDLE_TEXT)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE_TEXT = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        \"component_id\": component_id,\n"
        "        \"criterion_id\": criterion_id,\n"
        "        \"covers\": \"R-QUX-001\",\n"
        "        \"criterion_text\": BUNDLE_TEXT[\"criterion_text\"],\n"
        "        \"requirement_text\": BUNDLE_TEXT[\"requirement_text\"],\n"
        "        \"interface\": BUNDLE_TEXT[\"interface\"],\n"
        "        \"glossary\": BUNDLE_TEXT[\"glossary\"],\n"
        "        \"dependency_interfaces\": {},\n"
        "        \"testing\": BUNDLE_TEXT[\"testing\"],\n"
        "    }\n",
    )

    # test-probe stand-in: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = \"test-probe@1.4.0\"\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", \"a\") as fh:\n"
        "        fh.write(\"probe\\n\")\n"
        "    return ProbeReport()\n",
    )

    # The one cached generated test, with a correct header.
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        generated_test_source(),
    )


def make_author(log_path):
    def author(bundle):
        with open(log_path, "a") as fh:
            fh.write("author\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": generated_test_source(),
            },
        }

    return author


def test_dependency_loaded_by_path_passes_and_scores_full(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_fixture(repo_root, log_path)

    report = verifier_orchestrator.verify("comp-qux", repo_root, test_author=make_author(log_path))

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
    assert len(matching) == 1
    criterion = matching[0]
    assert field(criterion, "result") == "pass", criterion

    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") == 1.0