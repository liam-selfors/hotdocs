# hotdocs-criterion: sha256:1e42f0d1d47344c6ac62b5ac0d669f3091aa038cd9b1f49a9eef7a02007907fb
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def bundle_for(criterion_id):
    return {
        "component_id": "comp-qux",
        "criterion_id": criterion_id,
        "covers": "R-" + criterion_id[3:],
        "criterion_text": "Criterion text for " + criterion_id,
        "requirement_text": "Requirement text.",
        "interface": "Interface text.",
        "glossary": "Glossary text.",
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


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        " + repr("component_id") + ": component_id,\n"
        "        " + repr("criterion_id") + ": criterion_id,\n"
        "        " + repr("covers") + ": " + repr("R-") + " + criterion_id[3:],\n"
        "        " + repr("criterion_text") + ": " + repr("Criterion text for ") + " + criterion_id,\n"
        "        " + repr("requirement_text") + ": " + repr("Requirement text.") + ",\n"
        "        " + repr("interface") + ": " + repr("Interface text.") + ",\n"
        "        " + repr("glossary") + ": " + repr("Glossary text.") + ",\n"
        "        " + repr("dependency_interfaces") + ": dict(),\n"
        "        " + repr("testing") + ": " + repr("") + ",\n"
        "    }\n"
    )


def probe_source():
    return (
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return dict(ok=self.ok, findings=list(self.findings))\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return ProbeReport()\n"
    )


def acceptance_text(criterion_id, requirement_id, then_text):
    return (
        "# " + criterion_id + "\n"
        "\n"
        "Covers: " + requirement_id + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given comp-qux whose qux() returns 2 * 2\n"
        "When verify runs\n"
        "Then " + then_text + "\n"
        "```\n"
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Qux** - a fixture term.\n",
    )
    write(
        repo_root / "specs" / "product" / "qux-capability.md",
        "---\nid: P-QUX\ntitle: Qux capability\nstatus: draft\nowners: [qux-team]\n---\n\n"
        "# Qux capability\n\nQux computes a number.\n",
    )
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\nid: comp-qux\ntitle: Qux\nstatus: draft\nowners: [qux-team]\n"
        "depends_on: []\nrealizes: [P-QUX]\n---\n\n# Qux\n\n## Purpose\n\nComputes qux.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nqux() -> int\n```\n",
    )
    write(
        comp / "requirements" / "R-QUX-001.md",
        "# R-QUX-001\n\n**R-QUX-001** - `qux()` MUST return 4.\n",
    )
    write(
        comp / "requirements" / "R-QUX-002.md",
        "# R-QUX-002\n\n**R-QUX-002** - `qux()` MUST return 4 where specs exist.\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        acceptance_text("AC-QUX-001", "R-QUX-001", "qux returns 4"),
    )
    write(
        comp / "acceptance" / "AC-QUX-002.md",
        acceptance_text("AC-QUX-002", "R-QUX-002", "qux returns 4 and specs is a directory"),
    )

    write(repo_root / "gen" / "qux" / "qux.py", "def qux():\n    return 2 * 2\n")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())

    gt = repo_root / "verification" / "qux" / "generated-test"
    write(
        gt / "test_ac_qux_001.py",
        header_for("AC-QUX-001") + "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_qux_returns_four():\n"
        "    assert qux.qux() == 4\n",
    )
    write(
        gt / "test_ac_qux_002.py",
        header_for("AC-QUX-002") + "\n"
        "from pathlib import Path\n"
        "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_qux_returns_four_with_specs():\n"
        "    assert qux.qux() == 4\n"
        "    assert (Path.cwd() / " + repr("specs") + ").is_dir()\n",
    )
    return gt


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": {"category": "unexpected", "message": "test_author should not be called"},
            "file": None,
        }

    return test_author


def test_faulty_test_in_mutation_sandbox_fails_with_test_origin(tmp_path):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    gt = build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_test_author(log_path)
    )

    criteria = {c["id"]: c for c in field(report, "criteria")}
    first = criteria["AC-QUX-001"]
    second = criteria["AC-QUX-002"]

    assert first["result"] == "pass", first

    assert second["result"] == "fail", second
    assert second["failure_origin"] == "test", second
    assert second["failure_detail"]["message"] == "test fails in the mutation sandbox", second
    assert not (gt / "test_ac_qux_002.py").exists()

    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") is not None