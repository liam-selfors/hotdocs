import importlib
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_FAKE_PROVENANCE_TRACKER_TEMPLATE = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with open(r"__RECORDER_PATH__", "a", encoding="utf-8") as f:
        f.write("called\\n")
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
                                "message": "result.foo equals 1 failed",
                                "expected": 1,
                                "actual": 2,
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
        "not_ready_reasons": ["comp-foo: verification failed"],
    }
'''


def _write_fake_provenance_tracker(repo_root: Path, recorder_path: Path) -> None:
    dep_dir = repo_root / "gen" / "provenance-tracker"
    dep_dir.mkdir(parents=True, exist_ok=True)
    source = _FAKE_PROVENANCE_TRACKER_TEMPLATE.replace(
        "__RECORDER_PATH__", str(recorder_path)
    )
    (dep_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


def test_verification_results_shows_both_passing_and_failing_individually(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    recorder_path = tmp_path / "invocations.log"

    _write_fake_provenance_tracker(repo_root, recorder_path)

    review_packet_builder = importlib.import_module("review_packet_builder")

    packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

    assert recorder_path.exists()
    assert "called" in recorder_path.read_text(encoding="utf-8")

    verification_results = _get(packet, "verification_results")
    assert verification_results is not None

    comp_report = _get(verification_results, "comp-foo")
    assert comp_report is not None

    criteria = _get(comp_report, "criteria")
    assert criteria is not None
    assert len(criteria) == 2

    results_by_id = {_get(c, "id"): _get(c, "result") for c in criteria}
    assert results_by_id == {"AC-FOO-001": "pass", "AC-FOO-002": "fail"}

    requirement_results = _get(comp_report, "requirement_results")
    assert requirement_results is not None
    assert _get(requirement_results, "R-FOO-001") == "pass"
    assert _get(requirement_results, "R-FOO-002") == "fail"

    # The breakdown must retain both individual outcomes, not collapse them
    # into a single aggregate verdict.
    assert _get(requirement_results, "R-FOO-001") != _get(
        requirement_results, "R-FOO-002"
    )