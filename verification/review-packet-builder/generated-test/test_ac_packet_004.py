import review_packet_builder

import os
import pprint
import subprocess
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def lookup(mapping, key):
    if isinstance(mapping, dict):
        return mapping[key]
    return getattr(mapping, key)


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
        },
    ],
    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
    "interface_drift": False,
    "mutation_score": 0.9,
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
        "comp-foo: verification failed (AC-FOO-002)"
    ],
}


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "README.md").write_text("fixture repo\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")

    tracker_dir = root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    report_literal = pprint.pformat(VERIFY_REPORT, width=100)
    (tracker_dir / "provenance_tracker.py").write_text(
        "REPORT = " + report_literal + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (root / "NOTES.md").write_text("second commit\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "add provenance-tracker stand-in")
    return root


def test_verification_results_shows_each_criterion_individually(repo_root):
    packet = review_packet_builder.build_review_packet(["comp-foo"], Path(repo_root))

    verification_results = field(packet, "verification_results")
    report = lookup(verification_results, "comp-foo")

    criteria = field(report, "criteria")
    criteria = list(criteria)
    assert len(criteria) == 2, criteria

    by_id = {field(c, "id"): c for c in criteria}
    assert set(by_id) == {"AC-FOO-001", "AC-FOO-002"}

    assert field(by_id["AC-FOO-001"], "result") == "pass"
    assert field(by_id["AC-FOO-002"], "result") == "fail"

    requirement_results = field(report, "requirement_results")
    assert lookup(requirement_results, "R-FOO-001") == "pass"
    assert lookup(requirement_results, "R-FOO-002") == "fail"

    # Not only an aggregate verdict: the full breakdown is present alongside it.
    assert field(report, "overall") == "fail"