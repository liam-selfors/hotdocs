# hotdocs-criterion: sha256:4e22aa222f9c76c1036a93f4026f6499483de4e14230dbfadb95b1c7c66d9d7f
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
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        return True
    if out == "":
        return False
    if out.startswith("Z"):
        return False
    return True


def build_fixture(repo_root, pid_path, log_path):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Qux** — a fixture term.\n",
    )
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "---\n\n"
        "# Qux capability\n\n"
        "## Purpose\n\nFixture capability.\n\n"
        "## Scope\n\n- In scope: qux.\n",
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
        "## Purpose\n\nA fixture component.\n\n"
        "## Scope\n\n- In scope: qux_run.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n## Change log\n\n- Initial.\n",
    )
    write(
        comp / "requirements" / "R-QUX-001.md",
        "**R-QUX-001** — `qux_run(x)` MUST return x.\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a value 3\n"
        "When qux_run is called with it\n"
        "Then it returns 3\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nqux_run(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "gen" / "qux" / "qux.py", "")

    bundle = {
        "component_id": "comp-qux",
        "criterion_id": "AC-QUX-001",
        "covers": "R-QUX-001",
        "criterion_text": "Given a value 3\nWhen qux_run is called with it\nThen it returns 3",
        "requirement_text": "**R-QUX-001** — `qux_run(x)` MUST return x.",
        "interface": "# Library\n\nqux_run(x: int) -> int",
        "glossary": "# Glossary\n\n- **Qux** — a fixture term.",
        "dependency_interfaces": {},
        "testing": "",
    }
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n\n\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('assemble not used in this fixture')\n\n\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.4.0'\n\n\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n\n\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return ProbeReport()\n",
    )

    canonical = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    child_code = (
        "import os, time\n"
        "with open(" + repr(str(pid_path)) + ", 'w') as f:\n"
        "    f.write(str(os.getpid()))\n"
        "time.sleep(600)\n"
    )
    test_source = (
        "# hotdocs-criterion: sha256:" + digest + "\n"
        "import subprocess\n"
        "import sys\n"
        "import time\n\n"
        "CHILD_CODE = " + repr(child_code) + "\n\n\n"
        "def test_hangs_with_detached_child():\n"
        "    subprocess.Popen([sys.executable, '-c', CHILD_CODE], start_new_session=True)\n"
        "    time.sleep(600)\n"
    )
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        test_source,
    )
    return test_source


def make_test_author(log_path, content):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "verification/qux/generated-test/test_ac_qux_001.py", "content": content},
        }
    return test_author


def test_timeout_kills_whole_process_tree(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid_path = tmp_path / "child.pid"
    log_path = tmp_path / "author.log"
    content = build_fixture(repo_root, pid_path, log_path)

    monkeypatch.setattr(verifier_orchestrator, "DEFAULT_TEST_TIMEOUT", 5)

    pid = None
    try:
        start = time.monotonic()
        report = verifier_orchestrator.verify(
            "comp-qux", repo_root, test_author=make_test_author(log_path, content)
        )
        elapsed = time.monotonic() - start

        criteria = field(report, "criteria")
        matching = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
        assert len(matching) == 1, criteria
        assert field(matching[0], "result") == "fail", matching[0]

        assert elapsed < 60, "verify took " + repr(elapsed) + " seconds"

        time.sleep(2)

        assert pid_path.is_file(), "child never wrote its pid file"
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        assert not pid_running(pid), "child pid " + repr(pid) + " is still running"
    finally:
        if pid is None and pid_path.is_file():
            try:
                pid = int(pid_path.read_text(encoding="utf-8").strip())
            except ValueError:
                pid = None
        if pid is not None and pid_running(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass