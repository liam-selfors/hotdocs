# hotdocs-criterion: sha256:ec8a1d80542d903e6d28f2eb75f7741fc1f53155701db4352ae98cd866ab5f70
import hashlib
import json
import os
import shlex
import shutil
import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HASHED_FIELDS = {
    "criterion_text": "Given a passing test\nWhen it runs\nThen it passes",
    "requirement_text": "R-QUX-001 Qux MUST pass.",
    "interface": "# Library\n\n```\nbar(x)\n```",
    "glossary": "# Glossary",
    "testing": "",
}


def bundle_header():
    payload = json.dumps(
        {k: HASHED_FIELDS[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler"
    ).resolve().parents[1]


def python_adapter_source(provision_value):
    return (
        "KIND = 'python'\n"
        "\n"
        "def layout_errors(*args, **kwargs):\n"
        "    return []\n"
        "\n"
        "def surface(*args, **kwargs):\n"
        "    return " + repr({"names": []}) + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def strength_sites(*args, **kwargs):\n"
        "    return []\n"
        "\n"
        "def apply_site(*args, **kwargs):\n"
        "    return None\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_value) + "\n"
    )


def build_fixture(repo_root, variant):
    specs = repo_root / "specs"
    write(specs / "glossary.md", "# Glossary\n")
    write(
        specs / "product" / "qux.md",
        "---\nid: P-QUX\ntitle: Qux capability\nstatus: draft\nowners: [team]\n---\n\n"
        "# P-QUX\n\nQux capability.\n",
    )
    comp = specs / "components" / "qux"
    write(
        comp / "component.md",
        "---\nid: comp-qux\ntitle: Qux\nstatus: draft\nowners: [team]\n"
        "depends_on: []\nrealizes: [P-QUX]\n---\n\n# Qux\n\n## Purpose\n\nQux fixture.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(comp / "interface" / "library.md", "# Library\n\n```\nbar(x)\n```\n")
    write(comp / "requirements" / "R-QUX-001.md", "# R-QUX-001\n\n**R-QUX-001** - Qux MUST pass.\n")
    write(comp / "requirements" / "R-QUX-002.md", "# R-QUX-002\n\n**R-QUX-002** - bar(x) MUST return v equal to x.\n")
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\nCovers: R-QUX-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a passing test\nWhen it runs\nThen it passes\n```\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-002.md",
        "# AC-QUX-002\n\nCovers: R-QUX-002\nKind: compiled\n\n"
        "```gherkin\nGiven a n is 3\nWhen bar is invoked with [3]\nThen v equals 3\n```\n",
    )

    write(
        repo_root / "gen" / "qux" / "qux.py",
        "class Out:\n"
        "    def __init__(self, v):\n"
        "        self.v = v\n"
        "\n"
        "def bar(x):\n"
        "    return Out(x)\n",
    )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "FIELDS = " + repr(HASHED_FIELDS) + "\n"
        "COVERS = " + repr({"AC-QUX-001": "R-QUX-001", "AC-QUX-002": "R-QUX-002"}) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = dict(FIELDS)\n"
        "    bundle['component_id'] = component_id\n"
        "    bundle['criterion_id'] = criterion_id\n"
        "    bundle['covers'] = COVERS.get(criterion_id, '')\n"
        "    bundle['dependency_interfaces'] = dict()\n"
        "    return bundle\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return dict(ok=self.ok, findings=list(self.findings))\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return ProbeReport()\n",
    )

    src = live_root() / "pipeline" / "criterion-compiler"
    shutil.copytree(
        src,
        repo_root / "pipeline" / "criterion-compiler",
        ignore=shutil.ignore_patterns("__pycache__"),
    )

    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        bundle_header() + "\n"
        "\n"
        "def test_passes():\n"
        "    assert 1 + 1 == 2\n",
    )

    if variant == "failing":
        provision_value = {
            "ok": False,
            "reason": "python environment: broken",
            "versions": {},
            "lockfile_sha256": None,
            "interpreter": None,
        }
    else:
        wrapper = (repo_root / "wrapper.sh").resolve()
        log = (repo_root / "wrapper.log").resolve()
        wrapper.write_text(
            "#!/bin/sh\n"
            "echo called >> " + shlex.quote(str(log)) + "\n"
            "exec " + shlex.quote(sys.executable) + ' "$@"\n',
            encoding="utf-8",
        )
        os.chmod(wrapper, 0o755)
        provision_value = {
            "ok": True,
            "reason": "",
            "versions": {"python": "0.0"},
            "lockfile_sha256": None,
            "interpreter": str(wrapper),
        }
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        python_adapter_source(provision_value),
    )


def criteria_by_id(report):
    return {field(c, "id"): c for c in field(report, "criteria")}


def test_failing_python_adapter_fails_every_criterion_as_environment(tmp_path):
    repo_root = tmp_path.resolve()
    build_fixture(repo_root, "failing")

    report = verifier_orchestrator.verify("comp-qux", repo_root)

    by_id = criteria_by_id(report)
    assert set(by_id) >= {"AC-QUX-001", "AC-QUX-002"}
    for cid in ("AC-QUX-001", "AC-QUX-002"):
        c = by_id[cid]
        assert field(c, "result") == "fail", c
        assert field(c, "failure_origin") == "environment", c
        assert field(field(c, "failure_detail"), "message") == "python environment: broken", c


def test_wrapped_python_adapter_runs_every_criterion_under_its_interpreter(tmp_path):
    repo_root = tmp_path.resolve()
    build_fixture(repo_root, "wrapped")

    report = verifier_orchestrator.verify("comp-qux", repo_root)

    by_id = criteria_by_id(report)
    assert set(by_id) >= {"AC-QUX-001", "AC-QUX-002"}
    for cid in ("AC-QUX-001", "AC-QUX-002"):
        c = by_id[cid]
        assert field(c, "result") == "pass", c

    log = repo_root / "wrapper.log"
    assert log.is_file()
    lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line == "called"]
    assert len(lines) >= 2, lines