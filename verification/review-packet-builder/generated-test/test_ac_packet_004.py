import subprocess
import textwrap
from pathlib import Path

import review_packet_builder


PROVENANCE_TRACKER_SRC = textwrap.dedent("""
    def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        return {
            "scope": "blast-radius",
            "ready": False,
            "components": {
                "comp-foo": {
                    "hit": True,
                    "verification_report": {
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
                            },
                        ],
                        "requirement_results": {
                            "R-FOO-001": "pass",
                            "R-FOO-002": "fail",
                        },
                        "interface_drift": False,
                        "mutation_score": 1.0,
                        "overall": "fail",
                    },
                    "license_scan": {"blocked": False},
                    "secret_scan": {"flagged": False},
                }
            },
            "capabilities": {},
            "not_ready_reasons": [
                "comp-foo: verification failed",
            ],
        }


    def last_requirement_failures(component_id, repo_root):
        return []
    """)


def _init_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_root, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_root, check=True, capture_output=True,
    )
    marker = repo_root / "README.md"
    marker.write_text("placeholder\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=repo_root, check=True, capture_output=True,
    )


def _get(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def test_verification_results_shows_both_results_individually(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _init_repo(repo_root)

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "provenance_tracker.py").write_text(PROVENANCE_TRACKER_SRC)

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    verification_results = _get(packet, "verification_results")
    assert verification_results is not None

    comp_result = _get(verification_results, "comp-foo")
    assert comp_result is not None

    overall = _get(comp_result, "overall")
    criteria = _get(comp_result, "criteria")
    assert criteria is not None

    results_by_id = {}
    for criterion in criteria:
        crit_id = _get(criterion, "id")
        crit_result = _get(criterion, "result")
        results_by_id[crit_id] = crit_result

    assert results_by_id == {"AC-FOO-001": "pass", "AC-FOO-002": "fail"}

    assert set(results_by_id.values()) == {"pass", "fail"}
    assert overall == "fail"

    requirement_results = _get(comp_result, "requirement_results")
    assert requirement_results is not None
    assert _get(requirement_results, "R-FOO-001") == "pass"
    assert _get(requirement_results, "R-FOO-002") == "fail"