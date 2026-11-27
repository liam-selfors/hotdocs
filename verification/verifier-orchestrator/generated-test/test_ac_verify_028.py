# hotdocs-criterion: sha256:c7dd891aac35778848eb5847f3b6f7d1650f6cec59002695f9f8f451b522b59e
import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE_TEXT = {
    "criterion_text": "Given a hanging test When verify runs Then it times out",
    "requirement_text": "R-QUX-001 says a hanging test times out.",
    "interface": "# Library\n\nbar_qux(x) -> int\n",
    "glossary": "# Glossary\n",
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def hanging_test_source(pid_path):
    return (
        header_line() + "\n"
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "\n"
        "\n"
        "def test_hangs():\n"
        "    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'], start_new_session=True)\n"
        "    with open(" + repr(str(pid_path)) + ", 'w') as fh:\n"
        "        fh.write(str(child.pid))\n"
        "        fh.flush()\n"
        "    time.sleep(600)\n"
    )


def assembler_source():
    return (
        "BUNDLE_TEXT = " + repr(BUNDLE_TEXT) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-QUX-001',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
        "    bundle.update(BUNDLE_TEXT)\n"
        "    return bundle\n"
    )


def probe_source():
    return (
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return ProbeReport()\n"
    )


def mutation_scorer_source():
    return (
        "class MutationResult:\n"
        "    def __init__(self):\n"
        "        self.mutation_score = 1.0\n"
        "        self.mutation_error = None\n"
        "        self.faulty_tests = []\n"
        "        self.mutants = 0\n"
        "        self.killed = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'mutation_score': self.mutation_score,\n"
        "            'mutation_error': self.mutation_error,\n"
        "            'faulty_tests': list(self.faulty_tests),\n"
        "            'mutants': self.mutants,\n"
        "            'killed': self.killed,\n"
        "        }\n"
        "\n"
        "\n"
        "def score(component_id, repo_root, tests, environment):\n"
        "    return MutationResult()\n"
    )


def build_fixture(repo_root, pid_path):
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "depends_on: []\n"
        "realizes: [P-QUX]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    write(
        comp / "requirements" / "R-QUX-001.md",
        "# R-QUX-001\n\n**R-QUX-001** — A hanging test MUST time out.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nbar_qux(x) -> int\n```\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a hanging test\n"
        "When verify runs\n"
        "Then it times out\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "---\n"
        "\n"
        "# Qux capability\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    write(repo_root / "gen" / "qux" / "qux.py", "")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())
    write(
        repo_root / "gen" / "mutation-scorer" / "mutation_scorer.py",
        mutation_scorer_source(),
    )
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        hanging_test_source(pid_path),
    )


def pid_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    out = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
    ).stdout.strip()
    if not out:
        return False
    return not out.startswith("Z")


def test_ac_verify_028_timeout_kills_whole_tree(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    pid_dir = tmp_path / "pids"
    pid_dir.mkdir()
    pid_path = pid_dir / "child.pid"
    build_fixture(repo_root, pid_path)

    author_log = tmp_path / "author.log"
    content = hanging_test_source(pid_path)

    def author(bundle):
        with open(author_log, "a") as fh:
            fh.write("called\n")
        return {
            "model": "fake",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "test_ac_qux_001.py", "content": content},
        }

    monkeypatch.setattr(verifier_orchestrator, "DEFAULT_TEST_TIMEOUT", 5)

    outcome = {}

    def run():
        try:
            outcome["report"] = verifier_orchestrator.verify("comp-qux", repo_root, test_author=author)
        except BaseException as exc:  # pragma: no cover - reported below
            outcome["error"] = exc

    started = time.monotonic()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=90)
    elapsed = time.monotonic() - started

    child_pid = None
    try:
        assert not worker.is_alive(), "verify did not return within 90 seconds"
        assert "error" not in outcome, "verify raised: " + repr(outcome.get("error"))
        assert elapsed < 60, "verify took " + repr(elapsed) + " seconds"

        report = outcome["report"]
        criteria = field(report, "criteria")
        matching = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
        assert len(matching) == 1, repr(criteria)
        assert field(matching[0], "result") == "fail"

        assert pid_path.is_file(), "the test never wrote child.pid"
        child_pid = int(pid_path.read_text().strip())

        time.sleep(2)
        assert not pid_running(child_pid), "child " + repr(child_pid) + " still running"
    finally:
        if child_pid is None and pid_path.is_file():
            try:
                child_pid = int(pid_path.read_text().strip())
            except ValueError:
                child_pid = None
        if child_pid is not None and pid_running(child_pid):
            try:
                os.kill(child_pid, 9)
            except OSError:
                pass