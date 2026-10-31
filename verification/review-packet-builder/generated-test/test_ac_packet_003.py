import subprocess
from pathlib import Path

import review_packet_builder


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _init_git_repo(repo_root: Path) -> None:
    (repo_root / "specs").mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)
    (repo_root / "README.md").write_text("fixture repo\n")
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_root, check=True)


_FAKE_PROVENANCE_TRACKER_SOURCE = """
import json

INVOCATION_LOG = __INVOCATION_LOG_PATH__


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with open(INVOCATION_LOG, "a") as f:
        f.write(json.dumps({"changed_ids": changed_ids}))
        f.write(chr(10))

    verification_report_alpha = {
        "component_id": "comp-alpha",
        "criteria": [
            {"id": "AC-ALPHA-001", "covers": "R-ALPHA-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-ALPHA-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    verification_report_beta = {
        "component_id": "comp-beta",
        "criteria": [
            {"id": "AC-BETA-001", "covers": "R-BETA-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-BETA-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }

    provenance_alpha = {
        "hit": True,
        "verification_report": verification_report_alpha,
        "license_scan": {"blocked": False, "findings": []},
        "secret_scan": {"flagged": False, "findings": []},
    }
    provenance_beta = {
        "hit": True,
        "verification_report": verification_report_beta,
        "license_scan": {"blocked": False, "findings": []},
        "secret_scan": {"flagged": False, "findings": []},
    }

    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-alpha": provenance_alpha,
            "comp-beta": provenance_beta,
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
"""


def _write_fake_provenance_tracker(repo_root: Path, invocation_log: Path) -> None:
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    module_path = dep_dir / "provenance_tracker.py"
    source = _FAKE_PROVENANCE_TRACKER_SOURCE.replace(
        "__INVOCATION_LOG_PATH__", repr(str(invocation_log))
    )
    module_path.write_text(source)


def test_ac_packet_003_regenerated_components_matches_provenance_components(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_git_repo(repo_root)

    invocation_log = tmp_path / "invocations.jsonl"
    _write_fake_provenance_tracker(repo_root, invocation_log)

    packet = review_packet_builder.build_review_packet(
        changed_ids=["R-UNRELATED-001"], repo_root=repo_root
    )

    assert invocation_log.exists(), "provenance-tracker's check_readiness was never invoked"

    regenerated = _get(packet, "regenerated_components")
    assert sorted(regenerated) == ["comp-alpha", "comp-beta"]