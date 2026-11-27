# hotdocs-criterion: sha256:f159f98392111eb50190245796cbd6acef7d4a42612d33e8cd0defa0a9e4f86e
"""AC-VERIFY-008: re-running verify on unchanged content with a consistent
judge (and a consistent test_author) reproduces the same VerificationReport."""

import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def report_as_dict(report):
    if isinstance(report, dict):
        return report
    return report.to_dict()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "detfix"

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Thing** - a thing.\n",
    )
    write(
        repo_root / "specs" / "product" / "detfix-capability.md",
        "---\n"
        "id: P-DETFIX\n"
        "title: Detfix capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Detfix capability\n"
        "\n"
        "The detfix component computes things.\n",
    )
    write(
        comp / "component.md",
        "---\n"
        "id: comp-detfix\n"
        "title: Detfix\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: [P-DETFIX]\n"
        "---\n"
        "\n"
        "# Detfix\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component for determinism.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ncompute_value(x)\n```\n",
    )
    write(
        comp / "requirements" / "R-DETFIX-001.md",
        "# R-DETFIX-001\n\n**R-DETFIX-001** - The spec MUST be clear.\n",
    )
    write(
        comp / "requirements" / "R-DETFIX-002.md",
        "# R-DETFIX-002\n\n**R-DETFIX-002** - The module MUST import.\n",
    )
    write(
        comp / "acceptance" / "AC-DETFIX-001.md",
        "# AC-DETFIX-001\n"
        "\n"
        "Covers: R-DETFIX-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the detfix spec\n"
        "When a reviewer reads it\n"
        "Then it is clear\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-DETFIX-002.md",
        "# AC-DETFIX-002\n"
        "\n"
        "Covers: R-DETFIX-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the detfix module\n"
        "When it is imported\n"
        "Then no error is raised\n"
        "```\n",
    )

    # Code under test: an empty module, so there is no mutation site.
    write(repo_root / "gen" / "detfix" / "detfix.py", "")

    # spec-bundle-assembler stand-in.
    bundle_fields = {
        "requirement_text": "The requirement.",
        "interface": "# Library\n\ncompute_value(x)",
        "glossary": "# Glossary",
        "dependency_interfaces": {},
        "testing": "",
    }
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "COVERS = " + repr({"AC-DETFIX-001": "R-DETFIX-001",
                            "AC-DETFIX-002": "R-DETFIX-002"}) + "\n"
        "FIELDS = " + repr(bundle_fields) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': COVERS.get(criterion_id, 'R-DETFIX-001'),\n"
        "        'criterion_text': 'Given x When y Then z for ' + criterion_id,\n"
        "    }\n"
        "    bundle.update(FIELDS)\n"
        "    bundle['dependency_interfaces'] = dict(FIELDS['dependency_interfaces'])\n"
        "    return bundle\n",
    )

    # test-probe stand-in: every test passes its probe.
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


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("judge\n")
        return {"result": "pass", "rationale": "consistent rationale"}

    return judge


GENERATED_TEST_SOURCE = (
    "import detfix\n"
    "\n"
    "\n"
    "def test_module_imports():\n"
    "    assert detfix is not None\n"
)


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("test_author\n")
        criterion_id = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
        return {
            "component_id": "comp-detfix",
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/detfix/generated-test/test_ac_detfix_002.py",
                "content": GENERATED_TEST_SOURCE,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def test_verify_twice_gives_identical_reports(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    judge_log = tmp_path / "judge.log"
    author_log = tmp_path / "author.log"
    judge = make_judge(judge_log)
    test_author = make_test_author(author_log)

    report1 = verifier_orchestrator.verify(
        "comp-detfix", repo_root, judge=judge, test_author=test_author
    )
    report2 = verifier_orchestrator.verify(
        "comp-detfix", repo_root, judge=judge, test_author=test_author
    )

    # Sanity: the judge really ran in both verifications.
    judge_calls = judge_log.read_text(encoding="utf-8").splitlines()
    assert judge_calls.count("judge") >= 2

    # Sanity: both reports concern the fixture and its criteria.
    assert field(report1, "component_id") == "comp-detfix"
    ids1 = sorted(field(c, "id") for c in field(report1, "criteria"))
    assert ids1 == ["AC-DETFIX-001", "AC-DETFIX-002"]

    # Then: the two VerificationReports are identical.
    d1 = report_as_dict(report1)
    d2 = report_as_dict(report2)
    assert d1 == d2
    assert json.dumps(d1, sort_keys=True, default=str) == json.dumps(
        d2, sort_keys=True, default=str
    )

    for name in (
        "component_id",
        "criteria",
        "requirement_results",
        "interface_drift",
        "mutation_score",
        "mutation_error",
        "assets",
        "drivers",
        "overall",
    ):
        assert field(report1, name) == field(report2, name), name