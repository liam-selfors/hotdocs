# hotdocs-criterion: sha256:9ed904de9b1f8c1a870d11e86154081a0e5a5c2b72d2cce8995791f59301e3f5
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import verifier_orchestrator


FIVE_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "bar_value(x) -> Box\n"
    "```\n"
    "\n"
    "`bar_value` returns a `Box` whose `value` is `x`.\n"
)

BASE_BUNDLE = {
    "component_id": "comp-qux",
    "criterion_id": "AC-QUX-001",
    "covers": "R-QUX-001",
    "criterion_text": "Given a qux module\nWhen its test runs\nThen it passes",
    "requirement_text": "bar_value(x) MUST return a Box whose value is x.",
    "interface": LIBRARY_MD.strip(),
    "glossary": "",
    "dependency_interfaces": {},
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in FIVE_KEYS},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler"
    ).resolve().parents[1]


def python_adapter_source(report):
    return (
        'KIND = "python"\n'
        "\n"
        "def layout_errors(asset_file):\n"
        "    return []\n"
        "\n"
        "def surface(asset_file):\n"
        '    return {"names": []}\n'
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(report) + "\n"
        "\n"
        "def guidance():\n"
        '    return {"generator": "", "test_author": ""}\n'
        "\n"
        "def strength_sites(asset_file):\n"
        "    return []\n"
        "\n"
        "def apply_site(asset_file, site):\n"
        "    return None\n"
    )


def build_fixture(repo_root, python_report):
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "realizes: [P-QUX]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Returns boxed values.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: bar_value.\n"
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
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Qux capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Boxing values.\n",
    )
    write(
        comp / "requirements" / "R-QUX-001.md",
        "**R-QUX-001** - bar_value(x) MUST return a Box whose value is x.\n",
    )
    write(
        comp / "requirements" / "R-QUX-002.md",
        "**R-QUX-002** - bar_value(x).value MUST equal x.\n",
    )
    write(comp / "interface" / "library.md", LIBRARY_MD)
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
        "When its test runs\n"
        "Then it passes\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-002.md",
        "# AC-QUX-002\n"
        "\n"
        "Covers: R-QUX-002\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a n is 3\n"
        "When bar_value is invoked with [n]\n"
        "Then value equals 3\n"
        "```\n",
    )

    # Component code: no mutation sites.
    write(
        repo_root / "gen" / "qux" / "qux.py",
        "class Box:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "\n"
        "    def __getitem__(self, key):\n"
        "        return getattr(self, key)\n"
        "\n"
        "\n"
        "def bar_value(x):\n"
        "    return Box(x)\n",
    )

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BASE = " + repr(BASE_BUNDLE) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    d = dict(BASE)\n"
        "    d['component_id'] = component_id\n"
        "    d['criterion_id'] = criterion_id\n"
        "    d['covers'] = 'R-' + criterion_id[3:]\n"
        "    return d\n",
    )

    # test-probe stand-in: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class _Report:\n"
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
        "    return _Report()\n",
    )

    # Real criterion-compiler copied into repo_root.
    src = live_root() / "pipeline" / "criterion-compiler"
    shutil.copytree(
        src,
        repo_root / "pipeline" / "criterion-compiler",
        ignore=shutil.ignore_patterns("__pycache__"),
    )

    # Cached, current, passing generated test.
    cached = (
        header_for(BASE_BUNDLE) + "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_bar_value_boxes():\n"
        "    assert qux.bar_value(2).value == 2\n"
    )
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        cached,
    )

    # Fake python adapter.
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        python_adapter_source(python_report),
    )


def make_author(log_path):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("authored\n")
        return {
            "model": "fake",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": {"category": "unexpected", "message": "test_author should not be called"},
            "file": None,
        }

    return author


def criteria_by_id(report):
    return {c["id"]: c for c in field(report, "criteria")}


def test_failing_python_adapter_fails_both_criteria_as_environment(tmp_path):
    repo_root = tmp_path.resolve() / "repo"
    repo_root.mkdir()
    build_fixture(
        repo_root,
        {
            "ok": False,
            "reason": "python environment: broken",
            "versions": {},
            "lockfile_sha256": None,
            "interpreter": None,
        },
    )
    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_author(tmp_path / "author.log")
    )
    crits = criteria_by_id(report)
    assert set(crits) >= {"AC-QUX-001", "AC-QUX-002"}
    for cid in ("AC-QUX-001", "AC-QUX-002"):
        c = crits[cid]
        assert c["result"] == "fail", c
        assert c["failure_origin"] == "environment", c
        assert c["failure_detail"]["message"] == "python environment: broken", c


def test_wrapped_python_adapter_runs_every_pytest_under_wrapper(tmp_path):
    repo_root = tmp_path.resolve() / "repo"
    repo_root.mkdir()
    wrapper = repo_root / "wrapper.sh"
    log = repo_root / "wrapper.log"
    wrapper.write_text(
        "#!/bin/sh\n"
        "echo called >> " + str(log) + "\n"
        "exec " + os.path.abspath(sys.executable) + ' "$@"\n',
        encoding="utf-8",
    )
    os.chmod(wrapper, 0o755)
    build_fixture(
        repo_root,
        {
            "ok": True,
            "reason": "",
            "versions": {"python": "0.0"},
            "lockfile_sha256": None,
            "interpreter": str(wrapper),
        },
    )
    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_author(tmp_path / "author.log")
    )
    crits = criteria_by_id(report)
    for cid in ("AC-QUX-001", "AC-QUX-002"):
        assert crits[cid]["result"] == "pass", crits[cid]
    assert log.is_file()
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln == "called"]
    assert len(lines) >= 2, lines