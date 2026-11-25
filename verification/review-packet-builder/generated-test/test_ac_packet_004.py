# hotdocs-criterion: sha256:94db055b1cadda883074541b00fa80fcce2e67a0ea23cc52e1e211500a504191
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root), check=True, capture_output=True,
    )


def _build_fixture(repo_root, log_path):
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    _write(comp_dir / "requirements" / "R-FOO-001.md",
           "**R-FOO-001** — Foo MUST do the first thing.\n")
    _write(comp_dir / "requirements" / "R-FOO-002.md",
           "**R-FOO-002** — Foo MUST do the second thing.\n")
    _write(comp_dir / "acceptance" / "AC-FOO-001.md",
           "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n")
    _write(comp_dir / "acceptance" / "AC-FOO-002.md",
           "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n")
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(comp_dir / "interface" / "library.md", "# Library\n\n```\nfoo() -> None\n```\n")
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo():\n    return None\n")

    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
             "failure_detail": {"message": "result.foo equals 5 failed", "expected": 5, "actual": 3},
             "failure_origin": "implementation"},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "0" * 64,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "overall": "fail",
    }
    secret_scan = {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    license_scan = {"blocked": False, "matches": [], "gate_version": "license_scanner@1.0.0"}
    verify_report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report,
                "license_scan": license_scan,
                "secret_scan": secret_scan,
            }
        },
        "capabilities": {},
        "secret_scan": secret_scan,
        "not_ready_reasons": ["comp-foo: verification failed (R-FOO-002)"],
    }

    src = (
        "REPORT = " + repr(verify_report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return REPORT\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", src)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")


def _criteria_results(report):
    criteria = field(report, "criteria")
    out = {}
    for c in criteria:
        out[field(c, "id")] = field(c, "result")
    return out


def test_ac_packet_004_verification_results_per_criterion(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"
    _build_fixture(repo_root, log_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001", "R-FOO-002"], repo_root
    )

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert log_path.read_text(encoding="utf-8").strip() != ""

    verification_results = field(packet, "verification_results")
    assert "comp-foo" in verification_results
    report = verification_results["comp-foo"]

    # Not merely an aggregate verdict: each criterion's result is present.
    results = _criteria_results(report)
    assert results.get("AC-FOO-001") == "pass"
    assert results.get("AC-FOO-002") == "fail"

    req = field(report, "requirement_results")
    assert req.get("R-FOO-001") == "pass"
    assert req.get("R-FOO-002") == "fail"