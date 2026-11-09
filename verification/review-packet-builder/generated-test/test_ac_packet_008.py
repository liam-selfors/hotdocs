import subprocess
import tempfile
from pathlib import Path

import review_packet_builder


def _get(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _run_git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True)


PROVENANCE_TRACKER_STANDIN = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "blast-radius",
        "ready": True,
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
                        }
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 0.92,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False},
                "secret_scan": {"flagged": False},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


def test_residual_risk_includes_passing_component_with_low_mutation_score():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        _run_git(["init", "-q"], cwd=repo_root)
        (repo_root / "README.md").write_text("fixture repo\n")
        _run_git(["add", "-A"], cwd=repo_root)
        _run_git(
            [
                "-c", "user.email=test@example.com",
                "-c", "user.name=Test",
                "commit", "-q", "-m", "init",
            ],
            cwd=repo_root,
        )

        tracker_dir = repo_root / "gen" / "provenance-tracker"
        tracker_dir.mkdir(parents=True)
        (tracker_dir / "provenance_tracker.py").write_text(PROVENANCE_TRACKER_STANDIN)

        packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

        residual_risk = _get(packet, "residual_risk")
        assert residual_risk is not None

        matches = [
            entry for entry in residual_risk
            if _get(entry, "component_id") == "comp-foo"
        ]
        assert len(matches) == 1

        entry = matches[0]
        message = _get(entry, "message")
        assert isinstance(message, str)
        assert message
        assert "0.92" in message