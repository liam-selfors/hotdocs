# hotdocs-criterion: sha256:13ca14dc4fe3793179242d9e00a8ff201a434f7ff9ef57dc52687c1faf32fab4
"""AC-PACKET-003: regenerated_components lists exactly the keys of
provenance-tracker's check_readiness VerifyReport.components map."""

import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _verification_report(component_id, r_id, ac_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": ac_id, "covers": r_id, "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {r_id: "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
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
        "drivers": [],
        "overall": "pass",
    }


def _secret_scan():
    return {
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


def _license_scan():
    return {"blocked": False, "matches": [], "cache_hit": False}


def _provenance_check_result(component_id, r_id, ac_id):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, r_id, ac_id),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }


def _write_tracker_stand_in(repo_root, verify_report, log_path):
    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0,"
        " llm_backend=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return " + repr(verify_report) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (tracker_dir / "provenance_tracker.py").write_text(source)


def test_ac_packet_003_regenerated_components_are_tracker_component_keys(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    verify_report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-alpha": _provenance_check_result(
                "comp-alpha", "R-ALPHA-001", "AC-ALPHA-001"),
            "comp-beta": _provenance_check_result(
                "comp-beta", "R-BETA-001", "AC-BETA-001"),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [],
    }

    _write_tracker_stand_in(repo_root, verify_report, log_path)
    (repo_root / "README.md").write_text("fixture repo\n")

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    packet = review_packet_builder.build_review_packet(
        ["R-ALPHA-001", "R-BETA-001"], repo_root)

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text()

    regenerated = list(field(packet, "regenerated_components"))
    assert len(regenerated) == 2, regenerated
    assert sorted(regenerated) == ["comp-alpha", "comp-beta"]