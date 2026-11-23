# hotdocs-criterion: sha256:f6c997bf445d5b968652070a7e9e65fa27ae7809f4f5f44350c0ab7795540502
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import verifier_orchestrator


TEXTS = {
    "criterion_text": "qux criterion text",
    "requirement_text": "qux requirement text",
    "interface": "qux interface text",
    "glossary": "qux glossary text",
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def header_hex():
    payload = json.dumps(
        {k: TEXTS[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def live_root():
    return (Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler").resolve().parents[1]


FENCE = "```"


def build_fixture(repo_root):
    repo_root = Path(repo_root)

    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Qux** — a fixture term.\n")
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "---\n\n"
        "# Qux capability\n\n"
        "## Purpose\n\nDoubles numbers.\n\n"
        "## Scope\n\n- In scope: doubling.\n",
    )

    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "realizes: [P-QUX]\n"
        "---\n\n"
        "# Qux\n\n"
        "## Purpose\n\nDoubles a number.\n\n"
        "## Scope\n\n- In scope: doubling.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n\n" + FENCE + "\nqux_double(x: int) -> Box\n" + FENCE + "\n\n"
        "Returns an object whose `value` is twice `x`.\n",
    )
    write(
        comp / "requirements" / "R-QUX-001.md",
        "**R-QUX-001** — `qux_double(x)` MUST return an object whose `value` is `x * 2`.\n",
    )
    write(
        comp / "requirements" / "R-QUX-002.md",
        "**R-QUX-002** — `qux_double(2)` MUST return an object whose `value` is `4`.\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n\n"
        + FENCE + "gherkin\n"
        "Given the qux module\n"
        "When qux_double is called with 3\n"
        "Then its value is 6\n"
        + FENCE + "\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-002.md",
        "# AC-QUX-002\n\n"
        "Covers: R-QUX-002\n"
        "Kind: compiled\n\n"
        + FENCE + "gherkin\n"
        "Given a n is 2\n"
        "When qux_double is invoked with {\"x\": n}\n"
        "Then value equals 4\n"
        + FENCE + "\n",
    )

    write(
        repo_root / "gen" / "qux" / "qux.py",
        "class _Box(dict):\n"
        "    def __getattr__(self, name):\n"
        "        try:\n"
        "            return self[name]\n"
        "        except KeyError:\n"
        "            raise AttributeError(name)\n"
        "\n"
        "\n"
        "def qux_double(x):\n"
        "    return _Box(value=x * 2)\n",
    )

    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        "# hotdocs-criterion: sha256:" + header_hex() + "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_double_three():\n"
        "    assert qux.qux_double(3).value == 6\n",
    )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "TEXTS = " + repr(TEXTS) + "\n"
        "COVERS = " + repr({"AC-QUX-001": "R-QUX-001", "AC-QUX-002": "R-QUX-002"}) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': COVERS.get(criterion_id, ''),\n"
        "        'criterion_text': TEXTS['criterion_text'],\n"
        "        'requirement_text': TEXTS['requirement_text'],\n"
        "        'interface': TEXTS['interface'],\n"
        "        'glossary': TEXTS['glossary'],\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': TEXTS['testing'],\n"
        "    }\n"
        "    return bundle\n",
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
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
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

    src = live_root() / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def adapter_common():
    return (
        "from pathlib import Path\n"
        "\n"
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
        "\n"
        "\n"
    )


def plant_failing_adapter(repo_root):
    report = {
        "ok": False,
        "reason": "python environment: broken",
        "versions": {},
        "lockfile_sha256": None,
        "interpreter": None,
    }
    write(
        Path(repo_root) / "gen" / "kind-python" / "kind_python.py",
        adapter_common()
        + "def provision(repo_root):\n"
        "    return " + repr(report) + "\n",
    )


def plant_wrapped_adapter(repo_root):
    repo_root = Path(repo_root).resolve()
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
        adapter_common()
        + "def provision(repo_root):\n"
        "    return " + repr(report) + "\n",
    )
    return log


def make_test_author(log_path):
    content = (
        "# hotdocs-criterion: sha256:" + header_hex() + "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_double_three():\n"
        "    assert qux.qux_double(3).value == 6\n"
    )

    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("author\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "ignored.py", "content": content},
        }

    return author


def by_id(report):
    criteria = field(report, "criteria")
    return {field(c, "id"): c for c in criteria}


def test_failing_python_adapter_fails_every_runnable_criterion(tmp_path):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    build_fixture(repo_root)
    plant_failing_adapter(repo_root)

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_test_author(tmp_path / "author.log")
    )
    criteria = by_id(report)

    assert set(criteria) >= {"AC-QUX-001", "AC-QUX-002"}
    for cid in ("AC-QUX-001", "AC-QUX-002"):
        c = criteria[cid]
        assert field(c, "result") == "fail", (cid, c)
        assert field(c, "failure_origin") == "environment", (cid, c)
        detail = field(c, "failure_detail")
        assert field(detail, "message") == "python environment: broken", (cid, c)


def test_wrapped_python_adapter_runs_pytest_under_reported_interpreter(tmp_path):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    build_fixture(repo_root)
    log = plant_wrapped_adapter(repo_root)

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_test_author(tmp_path / "author.log")
    )
    criteria = by_id(report)

    assert set(criteria) >= {"AC-QUX-001", "AC-QUX-002"}
    for cid in ("AC-QUX-001", "AC-QUX-002"):
        assert field(criteria[cid], "result") == "pass", (cid, criteria[cid])

    assert log.is_file()
    lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line == "called"]
    assert len(lines) >= 2