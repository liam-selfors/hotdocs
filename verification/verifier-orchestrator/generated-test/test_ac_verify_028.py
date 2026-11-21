# hotdocs-criterion: sha256:d043c7867b3713583b4f68c6007ea69ab8b31badbf16430430cebc3c0bce4b9c
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pid_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        out = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:
        return True
    if out == "":
        return False
    if out.startswith("Z"):
        return False
    return True


def build_fixture(repo_root, pidfile, author_log):
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
        "Provides qux.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- qux\n",
    )
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
        "Computes qux values.\n"
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
        comp / "requirements" / "R-QUX-001.md",
        "**R-QUX-001** — `qux_run` MUST return an integer.\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a qux input of 1\n"
        "When qux_run is called\n"
        "Then it returns an integer\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "qux_run(x) -> int\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(repo_root / "gen" / "qux" / "qux.py", "")

    bundle = {
        "component_id": "comp-qux",
        "criterion_id": "AC-QUX-001",
        "covers": "R-QUX-001",
        "criterion_text": "Given a qux input of 1 When qux_run is called Then it returns an integer",
        "requirement_text": "R-QUX-001 qux_run MUST return an integer.",
        "interface": "qux_run(x) -> int",
        "glossary": "# Glossary",
        "dependency_interfaces": {},
        "testing": "",
    }
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "import copy\n"
        "\n"
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return copy.deepcopy(BUNDLE)\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('not used')\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n"
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
        "    return ProbeReport()\n",
    )

    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    header = "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    test_source = (
        header + "\n"
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "\n"
        "\n"
        "def test_spawns_detached_child():\n"
        "    child = subprocess.Popen(\n"
        "        [sys.executable, '-c', 'import time; time.sleep(600)'],\n"
        "        start_new_session=True,\n"
        "    )\n"
        "    with open(" + repr(str(pidfile)) + ", 'w') as fh:\n"
        "        fh.write(str(child.pid))\n"
        "    time.sleep(600)\n"
    )
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        test_source,
    )

    def test_author(b):
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": test_source,
            },
        }

    return test_author


def test_timeout_kills_whole_process_tree(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pidfile = tmp_path / "child.pid"
    author_log = tmp_path / "author.log"
    test_author = build_fixture(repo_root, pidfile, author_log)

    monkeypatch.setattr(verifier_orchestrator, "DEFAULT_TEST_TIMEOUT", 5)

    pid = None
    try:
        start = time.monotonic()
        report = verifier_orchestrator.verify("comp-qux", repo_root, judge=None, test_author=test_author)
        elapsed = time.monotonic() - start

        criteria = field(report, "criteria")
        matching = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
        assert len(matching) == 1
        assert field(matching[0], "result") == "fail"

        assert elapsed < 60, "verify took " + repr(elapsed) + " seconds"

        assert pidfile.is_file(), "the cached test never wrote child.pid"
        pid = int(pidfile.read_text(encoding="utf-8").strip())

        time.sleep(2)
        assert not pid_running(pid), "child process " + repr(pid) + " is still running"
    finally:
        if pid is None and pidfile.is_file():
            try:
                pid = int(pidfile.read_text(encoding="utf-8").strip())
            except ValueError:
                pid = None
        if pid is not None and pid_running(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass