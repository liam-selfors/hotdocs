import json
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
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


STAND_IN_TEMPLATE = '''
import json as _json

_LOG_PATH = {log_path!r}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(record) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{"fn": "check_readiness", "changed_ids": list(changed_ids) if changed_ids is not None else None}})
    return {{
        "scope": "blast-radius",
        "ready": True,
        "components": {{
            "comp-alpha": {{
                "hit": True,
                "verification_report": {{
                    "component_id": "comp-alpha",
                    "criteria": [
                        {{"id": "AC-ALPHA-001", "covers": "R-ALPHA-001", "kind": "compiled", "result": "pass"}}
                    ],
                    "requirement_results": {{"R-ALPHA-001": "pass"}},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                }},
                "license_scan": {{"blocked": False}},
                "secret_scan": {{"flagged": False}},
            }},
            "comp-beta": {{
                "hit": True,
                "verification_report": {{
                    "component_id": "comp-beta",
                    "criteria": [
                        {{"id": "AC-BETA-001", "covers": "R-BETA-001", "kind": "compiled", "result": "pass"}}
                    ],
                    "requirement_results": {{"R-BETA-001": "pass"}},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                }},
                "license_scan": {{"blocked": False}},
                "secret_scan": {{"flagged": False}},
            }},
        }},
        "capabilities": {{}},
        "not_ready_reasons": [],
    }}


def last_requirement_failures(component_id, repo_root):
    _log({{"fn": "last_requirement_failures", "component_id": component_id}})
    return []
'''


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    (repo_root / "README.md").write_text("fixture repo\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "initial")

    log_path = tmp_path / "provenance_tracker_calls.jsonl"
    stand_in_dir = repo_root / "gen" / "provenance-tracker"
    stand_in_dir.mkdir(parents=True)
    (stand_in_dir / "provenance_tracker.py").write_text(
        STAND_IN_TEMPLATE.format(log_path=str(log_path)), encoding="utf-8"
    )
    return repo_root, log_path


def test_regenerated_components_are_exactly_check_readiness_component_keys(tmp_path):
    repo_root, log_path = _make_repo(tmp_path)

    packet = review_packet_builder.build_review_packet(["R-ALPHA-001"], repo_root)

    # The stand-in provenance-tracker was actually consulted.
    assert log_path.exists(), "provenance-tracker stand-in check_readiness was never called"
    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(c["fn"] == "check_readiness" for c in calls)

    regenerated = list(field(packet, "regenerated_components"))
    assert len(regenerated) == 2, regenerated
    assert sorted(regenerated) == ["comp-alpha", "comp-beta"]