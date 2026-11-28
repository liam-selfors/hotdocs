# hotdocs-criterion: sha256:b96de43c485921df141bfd7e3fac42e87735582f2ac2ab968829e992c4793cc0
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }


def _secret_scan_result():
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


def _provenance_check_result(component_id, r_id, ac_id):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, r_id, ac_id),
        "license_scan": {"blocked": False},
        "secret_scan": _secret_scan_result(),
    }


def _init_git_repo(repo_root):
    def git(*args):
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
             "-c", "commit.gpgsign=false"] + list(args),
            cwd=str(repo_root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    git("init", "-q")
    (repo_root / "README.md").write_text("fixture\n")
    git("add", "-A")
    git("commit", "-q", "-m", "initial")


def _write_tracker_stand_in(repo_root, report, log_path):
    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "REPORT = " + repr(report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (tracker_dir / "provenance_tracker.py").write_text(source)


def test_regenerated_components_are_exactly_verify_report_component_keys(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_git_repo(repo_root)

    log_path = tmp_path / "tracker_calls.log"
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-alpha": _provenance_check_result("comp-alpha", "R-ALPHA-001", "AC-ALPHA-001"),
            "comp-beta": _provenance_check_result("comp-beta", "R-BETA-001", "AC-BETA-001"),
        },
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [],
    }
    _write_tracker_stand_in(repo_root, report, log_path)

    packet = review_packet_builder.build_review_packet(["R-ALPHA-001"], repo_root)

    assert log_path.is_file(), "provenance-tracker stand-in check_readiness was never called"
    assert "check_readiness" in log_path.read_text()

    regenerated = list(field(packet, "regenerated_components"))
    assert len(regenerated) == 2
    assert sorted(regenerated) == ["comp-alpha", "comp-beta"]