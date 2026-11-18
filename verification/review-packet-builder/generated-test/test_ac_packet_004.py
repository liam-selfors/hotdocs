# hotdocs-criterion: sha256:74e7d3b284a63a5bffbe6b6e9c26f587e17a1aee08da4fa8503f90018509b42b
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {
            "id": "AC-FOO-001",
            "covers": "R-FOO-001",
            "kind": "compiled",
            "result": "pass",
        },
        {
            "id": "AC-FOO-002",
            "covers": "R-FOO-002",
            "kind": "compiled",
            "result": "fail",
            "failure_detail": {
                "message": "result.foo equals 5 failed",
                "expected": 5,
                "actual": 3,
            },
            "failure_origin": "implementation",
        },
    ],
    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
    "interface_drift": False,
    "mutation_score": None,
    "mutation_error": None,
    "overall": "fail",
}

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": False,
    "components": {
        "comp-foo": {
            "hit": True,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": {"blocked": False, "findings": []},
            "secret_scan": {"flagged": False, "findings": []},
        }
    },
    "capabilities": {},
    "not_ready_reasons": [
        "comp-foo: verification failed (R-FOO-002)",
    ],
}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(repo_root, *args):
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"

    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the first thing.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — Foo MUST do the second thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "Given foo\nWhen it runs\nThen the first thing happens\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "Given foo\nWhen it runs\nThen the second thing happens\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo() -> None\n```\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo():\n    return None\n")

    tracker_src = (
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        tracker_src,
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "commit.gpgsign", "false")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    return repo_root, log_path


def test_verification_results_show_each_criterion_individually(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001", "R-FOO-002"], repo_root
    )

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text().splitlines()

    verification_results = field(packet, "verification_results")
    assert "comp-foo" in verification_results
    report = verification_results["comp-foo"]

    # Not merely an aggregate verdict: a per-criterion breakdown must be present.
    assert not isinstance(report, (str, bool))
    criteria = field(report, "criteria")
    assert isinstance(criteria, (list, tuple))

    by_id = {field(c, "id"): field(c, "result") for c in criteria}
    assert by_id.get("AC-FOO-001") == "pass"
    assert by_id.get("AC-FOO-002") == "fail"

    results = sorted(field(c, "result") for c in criteria)
    assert "pass" in results and "fail" in results