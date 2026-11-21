# hotdocs-criterion: sha256:afabc294870ba6ab00d27b0c4e9a2b6bdf2daadadc5af2934cf8e7ee506bf6cd
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FIVE = ("criterion_text", "requirement_text", "interface", "glossary", "testing")

INTERFACE_TEXT = "# Library\n\n```\nqux_pair(x) -> Pair\n```"
GLOSSARY_TEXT = "# Glossary\n\n- **Qux** - a fixture term."

BUNDLES = {
    "AC-QUX-001": {
        "component_id": "comp-qux",
        "criterion_id": "AC-QUX-001",
        "covers": "R-QUX-001",
        "criterion_text": "Given qux exists When anything is checked Then it holds",
        "requirement_text": "R-QUX-001 qux_pair MUST exist.",
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": "",
    },
    "AC-QUX-002": {
        "component_id": "comp-qux",
        "criterion_id": "AC-QUX-002",
        "covers": "R-QUX-002",
        "criterion_text": "Given a n is 3 When qux_pair is invoked with [n] Then value equals 3",
        "requirement_text": "R-QUX-002 qux_pair MUST return its argument as value.",
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": "",
    },
}


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in FIVE},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PASSING_TEST_BODY = (
    "\n"
    "\n"
    "def test_ac_qux_001_holds():\n"
    "    assert 1 + 1 == 2\n"
)


def python_adapter_source(provision_report):
    return (
        "KIND = 'python'\n"
        "\n"
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def surface(asset_file):\n"
        "    return {'names': []}\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return dict(" + repr(provision_report) + ")\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return {'generator': '', 'test_author': ''}\n"
        "\n"
        "\n"
        "def asset_runner(asset_file):\n"
        "    def run(entry, args):\n"
        "        raise RuntimeError('not used')\n"
        "    return run\n"
        "\n"
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )


def build_fixture(repo_root, variant):
    # product capability
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\nid: P-QUX\ntitle: Qux capability\nstatus: draft\nowners: [team]\n---\n\n"
        "# Qux capability\n\n## Purpose\n\nQux.\n\n## Scope\n\n- qux\n\n"
        "### CS-QUX-001\n\nCovers: P-QUX\n\n```gherkin\nGiven a n is 1\n"
        "When qux_pair is invoked with [n]\nThen value equals 1\n```\n",
    )
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT + "\n")

    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\nid: comp-qux\ntitle: Qux\nstatus: draft\nowners: [team]\nrealizes: [P-QUX]\n---\n\n"
        "# Qux\n\n## Purpose\n\nPairs a value.\n\n## Scope\n\n- In scope: qux_pair.\n\n"
        "## Definitions\n\nNone.\n\n## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n## Change log\n\n- Initial.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(comp / "interface" / "library.md", INTERFACE_TEXT + "\n")
    write(
        comp / "requirements" / "R-QUX-001.md",
        "# R-QUX-001\n\n**R-QUX-001** - qux_pair MUST exist.\n",
    )
    write(
        comp / "requirements" / "R-QUX-002.md",
        "# R-QUX-002\n\n**R-QUX-002** - qux_pair MUST return its argument as value.\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\nCovers: R-QUX-001\nKind: generated-test\n\n"
        "```gherkin\nGiven qux exists\nWhen anything is checked\nThen it holds\n```\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-002.md",
        "# AC-QUX-002\n\nCovers: R-QUX-002\nKind: compiled\n\n"
        "```gherkin\nGiven a n is 3\nWhen qux_pair is invoked with [n]\nThen value equals 3\n```\n",
    )

    # component code
    write(
        repo_root / "gen" / "qux" / "qux.py",
        "from types import SimpleNamespace\n"
        "\n"
        "\n"
        "def qux_pair(x):\n"
        "    return SimpleNamespace(value=x)\n",
    )

    # spec-bundle-assembler stand-in
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLES = " + repr(BUNDLES) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLES[criterion_id])\n",
    )

    # test-probe stand-in
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )

    # real criterion-compiler copied into repo_root
    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler"
    ).resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))

    # cached, current, passing generated test
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        header_for(BUNDLES["AC-QUX-001"]) + "\n" + PASSING_TEST_BODY.lstrip("\n"),
    )

    # python adapter
    if variant == "failing":
        report = {
            "ok": False,
            "reason": "python environment: broken",
            "versions": {},
            "lockfile_sha256": None,
            "interpreter": None,
        }
    else:
        wrapper = repo_root / "wrapper.sh"
        log = repo_root / "wrapper.log"
        wrapper.write_text(
            "#!/bin/sh\n"
            + "echo called >> " + str(log) + "\n"
            + "exec " + sys.executable + ' "$@"\n',
            encoding="utf-8",
        )
        os.chmod(wrapper, 0o755)
        report = {
            "ok": True,
            "reason": "",
            "versions": {"python": "0.0"},
            "lockfile_sha256": None,
            "interpreter": str(wrapper),
        }
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        python_adapter_source(report),
    )


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        b = {k: (bundle[k] if isinstance(bundle, dict) else getattr(bundle, k)) for k in FIVE}
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": header_for(b) + "\n" + PASSING_TEST_BODY.lstrip("\n"),
            },
        }

    return test_author


def criteria_by_id(report):
    return {c["id"]: c for c in field(report, "criteria")}


def test_failing_python_adapter_fails_both_criteria_as_environment(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "failing")

    report = verifier_orchestrator.verify(
        "comp-qux",
        repo_root,
        test_author=make_test_author(tmp_path / "author.log"),
    )

    crits = criteria_by_id(report)
    assert set(crits) >= {"AC-QUX-001", "AC-QUX-002"}
    for cid in ("AC-QUX-001", "AC-QUX-002"):
        c = crits[cid]
        assert c["result"] == "fail", c
        assert c["failure_origin"] == "environment", c
        assert c["failure_detail"]["message"] == "python environment: broken", c


def test_wrapped_python_adapter_runs_every_pytest_under_wrapper(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, "wrapped")

    report = verifier_orchestrator.verify(
        "comp-qux",
        repo_root,
        test_author=make_test_author(tmp_path / "author.log"),
    )

    crits = criteria_by_id(report)
    assert crits["AC-QUX-001"]["result"] == "pass", crits["AC-QUX-001"]
    assert crits["AC-QUX-002"]["result"] == "pass", crits["AC-QUX-002"]

    log = repo_root / "wrapper.log"
    assert log.is_file()
    lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line == "called"]
    assert len(lines) >= 2, lines