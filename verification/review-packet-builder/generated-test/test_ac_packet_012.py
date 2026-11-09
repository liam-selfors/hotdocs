import json
import os
import re
import subprocess

import review_packet_builder


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _git(repo, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test Fixture"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Fixture"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _make_repo(tmp_path, name, tracker_source):
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q")
    tracker_dir = repo / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "provenance_tracker.py").write_text(tracker_source)
    (repo / "README.md").write_text("fixture repo\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial commit")
    return repo


TRACKER_REAL_CONTENT = '''
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
                        },
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 0.92,
                    "overall": "pass",
                },
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


TRACKER_USAGE_ERROR = '''
class UsageError(Exception):
    pass


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    raise UsageError("provenance-tracker usage error")


def last_requirement_failures(component_id, repo_root):
    return []
'''


TRACKER_AZ_RESULT = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {"z": 1, "a": 2},
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


def test_build_json_has_real_content_and_exemption_fields(tmp_path, capsys):
    repo = _make_repo(tmp_path, "repo_scenario1", TRACKER_REAL_CONTENT)

    rc = review_packet_builder.main(
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            f"--repo-root={repo}",
            "--format=json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0

    packet = json.loads(captured.out)

    verification_results = _get(packet, "verification_results")
    assert verification_results
    comp_foo_result = _get(verification_results, "comp-foo")
    assert comp_foo_result is not None
    assert _get(comp_foo_result, "overall") == "pass"

    residual_risk = _get(packet, "residual_risk")
    assert residual_risk
    assert any(
        _get(entry, "component_id") == "comp-foo"
        and "mutation_score" in (_get(entry, "message") or "")
        for entry in residual_risk
    )

    exemption_changes = _get(packet, "exemption_changes")
    assert exemption_changes is not None
    assert _get(exemption_changes, "sealed") == []
    assert _get(exemption_changes, "pinned_overrides") == []


def test_changed_requirements_filters_to_r_id_shaped_subset(tmp_path, capsys):
    repo = _make_repo(tmp_path, "repo_scenario2", TRACKER_REAL_CONTENT)

    rc = review_packet_builder.main(
        [
            "review-packet",
            "build",
            "--changed",
            "R-FOO-001",
            "--changed",
            "comp-foo",
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0

    packet = json.loads(captured.out)
    assert _get(packet, "changed_requirements") == ["R-FOO-001"]


def test_usage_errors_exit_2(tmp_path):
    repo = _make_repo(tmp_path, "repo_scenario3", TRACKER_REAL_CONTENT)
    repo_str = str(repo)

    usage_argvs = [
        ["review-packet", "build", f"--repo-root={repo_str}"],
        ["review-packet", "serve", "--changed=R-FOO-001"],
        ["review-packet"],
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            f"--repo-root={repo_str}",
            "--changed",
        ],
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            f"--repo-root={repo_str}",
            "--repo-root",
        ],
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            f"--repo-root={repo_str}",
            "--format",
        ],
    ]

    for argv in usage_argvs:
        rc = review_packet_builder.main(list(argv))
        assert rc == 2, f"expected exit 2 for argv={argv!r}, got {rc!r}"


def test_invalid_format_exits_2(tmp_path):
    repo = _make_repo(tmp_path, "repo_scenario4", TRACKER_REAL_CONTENT)

    rc = review_packet_builder.main(
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            f"--repo-root={repo}",
            "--format=bogus",
        ]
    )
    assert rc == 2


def test_upstream_usage_error_exits_1(tmp_path):
    repo = _make_repo(tmp_path, "repo_scenario5", TRACKER_USAGE_ERROR)

    rc = review_packet_builder.main(
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            f"--repo-root={repo}",
        ]
    )
    assert rc == 1


def test_json_values_are_sort_keyed_in_both_formats(tmp_path, capsys):
    repo = _make_repo(tmp_path, "repo_scenario6", TRACKER_AZ_RESULT)

    rc_json = review_packet_builder.main(
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            f"--repo-root={repo}",
            "--format=json",
        ]
    )
    out_json = capsys.readouterr().out
    assert rc_json == 0

    match_json = re.search(r'"comp-foo":\s*\{(.*?)\}', out_json, re.DOTALL)
    assert match_json is not None, out_json
    inner_json = match_json.group(1)
    assert inner_json.index('"a"') < inner_json.index('"z"')

    rc_md = review_packet_builder.main(
        [
            "review-packet",
            "build",
            "--changed=R-FOO-001",
            f"--repo-root={repo}",
        ]
    )
    out_md = capsys.readouterr().out
    assert rc_md == 0

    match_md = re.search(r"comp-foo:\s*(.*)", out_md)
    assert match_md is not None, out_md
    line_md = match_md.group(1)
    assert line_md.index("a") < line_md.index("z")