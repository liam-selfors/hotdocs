# hotdocs-criterion: sha256:2e383cb05d82c44d2b8e8f99446efd9df132a524c17e733ccc891a2dd3da25ac
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


CRITERION_TEXT = (
    "Given a qux process that sleeps\n"
    "When qux_run is invoked\n"
    "Then it times out"
)
REQUIREMENT_TEXT = "**R-QUX-001** - qux_run MUST run."
INTERFACE_TEXT = "# Library\n\n```\nqux_run() -> None\n```\n"


def bundle_dict():
    return {
        "component_id": "comp-qux",
        "criterion_id": "AC-QUX-001",
        "covers": "R-QUX-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_test_source(bundle, pid_file):
    return (
        header_for(bundle) + "\n"
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "\n"
        "\n"
        "def test_spawns_and_sleeps():\n"
        "    child = subprocess.Popen(\n"
        "        [sys.executable, '-c', 'import time; time.sleep(600)'],\n"
        "        start_new_session=True,\n"
        "    )\n"
        "    with open(" + repr(str(pid_file)) + ", 'w') as fh:\n"
        "        fh.write(str(child.pid))\n"
        "    time.sleep(600)\n"
    )


def build_fixture(repo_root, pid_file, author_log):
    bundle = bundle_dict()

    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\nid: P-QUX\ntitle: Qux capability\nstatus: draft\nowners: [team]\n---\n\n"
        "# Qux capability\n\n## Purpose\n\nQux.\n\n## Scope\n\n- qux\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\nid: comp-qux\ntitle: Qux\nstatus: draft\nowners: [team]\nrealizes: [P-QUX]\n---\n\n"
        "# Qux\n\n## Purpose\n\nRuns qux.\n\n## Scope\n\n- In scope: qux.\n\n"
        "## Definitions\n\nNone.\n\n## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n## Change log\n\n- Initial.\n",
    )
    write(comp / "requirements" / "R-QUX-001.md", "# R-QUX-001\n\n" + REQUIREMENT_TEXT + "\n")
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\nCovers: R-QUX-001\nKind: generated-test\n\n"
        "```gherkin\n" + CRITERION_TEXT + "\n```\n",
    )

    write(repo_root / "gen" / "qux" / "qux.py", "")

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(" + repr(bundle) + ")\n",
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

    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        cached_test_source(bundle, pid_file),
    )

    content = cached_test_source(bundle, pid_file)

    def test_author(b):
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "verification/qux/generated-test/test_ac_qux_001.py", "content": content},
        }

    def judge(b):
        return {"result": "pass", "rationale": "fake"}

    return test_author, judge


def pid_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        out = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return True
    if not out:
        return False
    return not out.startswith("Z")


def test_ac_verify_028_timeout_kills_whole_process_tree(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid_file = tmp_path / "child.pid"
    author_log = tmp_path / "author.log"
    test_author, judge = build_fixture(repo_root, pid_file, author_log)

    monkeypatch.setattr(verifier_orchestrator, "DEFAULT_TEST_TIMEOUT", 5)

    child_pid = None
    try:
        start = time.monotonic()
        report = verifier_orchestrator.verify(
            "comp-qux", repo_root, judge=judge, test_author=test_author
        )
        elapsed = time.monotonic() - start

        criteria = field(report, "criteria")
        matching = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
        assert len(matching) == 1, criteria
        assert field(matching[0], "result") == "fail", matching[0]

        assert elapsed < 60, elapsed

        assert pid_file.is_file(), "the cached test never wrote child.pid"
        child_pid = int(pid_file.read_text().strip())

        time.sleep(2)
        assert not pid_running(child_pid), "child pid " + str(child_pid) + " is still running"
    finally:
        if child_pid is None and pid_file.is_file():
            try:
                child_pid = int(pid_file.read_text().strip())
            except ValueError:
                child_pid = None
        if child_pid is not None and pid_running(child_pid):
            try:
                os.kill(child_pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass