import review_packet_builder

import os
import subprocess
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id):
    return {
        "component_id": component_id,
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
        "mutation_score": 1.0,
        "overall": "pass",
    }


def _provenance_check_result(component_id):
    return {
        "hit": True,
        "verification_report": _verification_report(component_id),
        "license_scan": {"blocked": False, "findings": []},
        "secret_scan": {"flagged": False, "findings": []},
    }


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
    )
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _build_repo(tmp_path, log_path, report):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "commit.gpgsign", "false")

    (repo_root / "README.md").write_text("fixture repo\n", encoding="utf-8")

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    tracker_source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    (tracker_dir / "provenance_tracker.py").write_text(tracker_source, encoding="utf-8")

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial fixture commit")
    return repo_root


def test_regenerated_components_lists_exactly_the_two_components(tmp_path):
    log_path = tmp_path / "tracker_invocations.log"
    component_ids = ["comp-alpha", "comp-beta"]
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {cid: _provenance_check_result(cid) for cid in component_ids},
        "capabilities": {},
        "not_ready_reasons": [],
    }
    repo_root = _build_repo(tmp_path, log_path, report)

    packet = review_packet_builder.build_review_packet(
        ["comp-alpha", "comp-beta"], Path(repo_root)
    )

    # The stand-in provenance-tracker must actually have been consulted.
    assert log_path.exists(), "provenance-tracker stand-in check_readiness was never called"
    calls = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    assert "check_readiness" in calls

    regenerated = list(field(packet, "regenerated_components"))
    assert len(regenerated) == 2, regenerated
    assert sorted(regenerated) == sorted(component_ids)