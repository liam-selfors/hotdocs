# hotdocs-criterion: sha256:97084e703f1367fdcd0e8156a915264b87d7c2059fca1dbcb23b977eccb85b89
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "provenance_tracker_calls.log"

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do the first thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-002.md",
        "**R-FOO-002** — Foo MUST do the second thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "Given foo\nWhen it runs\nThen it does the first thing\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "Given foo\nWhen it runs\nThen it does the second thing\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "VALUE = 1\n")

    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "result.foo equals 5 failed", "expected": 5, "actual": 3},
                "failure_origin": "implementation",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "fail",
    }
    verify_report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report,
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": ["comp-foo: verification failed (R-FOO-002)"],
    }

    stand_in = (
        "VERIFY_REPORT = " + repr(verify_report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return VERIFY_REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", stand_in)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")

    return repo_root, log_path


def test_ac_packet_004_verification_results_per_criterion(tmp_path):
    repo_root, log_path = _build_fixture(tmp_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001", "R-FOO-002"], repo_root
    )

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8")

    verification_results = field(packet, "verification_results")
    assert "comp-foo" in verification_results
    report = verification_results["comp-foo"]

    # Not merely an aggregate verdict: must be a structured report.
    assert not isinstance(report, (str, bool)), report
    assert has_field(report, "criteria"), report
    criteria = field(report, "criteria")
    assert isinstance(criteria, (list, tuple))

    results_by_id = {field(c, "id"): field(c, "result") for c in criteria}
    assert results_by_id.get("AC-FOO-001") == "pass", results_by_id
    assert results_by_id.get("AC-FOO-002") == "fail", results_by_id