# hotdocs-criterion: sha256:afd8d3969cb332c61df786ffea70e612f79bdb3a5bd2c45743ae4eaec6e646db
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root), check=True, capture_output=True,
    )


def _verification_report(component_id, req_id, ac_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": ac_id, "covers": req_id, "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {req_id: "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "0" * 64,
                    "versions": {"python": "3.12.4"},
                    "lockfile_sha256": None}],
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
    return {
        "blocked": False,
        "matches": [],
        "gate_version": "license_scanner@1.0.0",
        "cache_hit": False,
    }


def _provenance_check_result(component_id, req_id, ac_id):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, req_id, ac_id),
        "license_scan": _license_scan(),
        "secret_scan": _secret_scan(),
    }


def test_ac_packet_003(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": _provenance_check_result("comp-foo", "R-FOO-001", "AC-FOO-001"),
            "comp-bar": _provenance_check_result("comp-bar", "R-BAR-001", "AC-BAR-001"),
        },
        "capabilities": {},
        "secret_scan": None,
        "not_ready_reasons": [],
    }

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (tracker_dir / "provenance_tracker.py").write_text(source)

    (repo_root / "README.md").write_text("fixture\n")
    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    packet = review_packet_builder.build_review_packet(["R-FOO-001"], repo_root)

    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text()

    regenerated = list(field(packet, "regenerated_components"))
    assert len(regenerated) == 2
    assert sorted(regenerated) == ["comp-bar", "comp-foo"]