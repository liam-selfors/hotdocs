import json
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report():
    # "z" deliberately inserted before "a" so sort_keys ordering is observable.
    report = {}
    report["z"] = 1
    report["a"] = 2
    report["component_id"] = "comp-foo"
    report["criteria"] = [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "llm-judge", "result": "skipped", "rationale": None},
    ]
    report["requirement_results"] = {"R-FOO-001": "pass", "R-FOO-002": "fail"}
    report["interface_drift"] = False
    report["mutation_score"] = 0.5
    report["overall"] = "pass"
    return report


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": _verification_report(),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=str(repo),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _make_repo(root, tracker_source):
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    (root / "README.md").write_text("fixture repo\n")
    tracker_dir = root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "provenance_tracker.py").write_text(tracker_source)
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


GOOD_TRACKER = (
    "import copy\n"
    "\n"
    "REPORT = " + repr(_verify_report()) + "\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return copy.deepcopy(REPORT)\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)

RAISING_TRACKER = (
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    raise ValueError('capability P-FOO needs a fresh run but no model was given')\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


@pytest.fixture
def repo(tmp_path):
    return _make_repo(tmp_path / "repo", GOOD_TRACKER)


@pytest.fixture
def raising_repo(tmp_path):
    return _make_repo(tmp_path / "raising_repo", RAISING_TRACKER)


def run_main(argv):
    try:
        rc = review_packet_builder.main(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            rc = 0
        elif isinstance(code, int):
            rc = code
        else:
            rc = 1
    return rc


def test_json_packet_has_real_content(repo, capsys):
    rc = run_main([
        "review-packet", "build", "--changed=R-FOO-001",
        "--repo-root=" + str(repo), "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    packet = json.loads(out)

    vr = packet["verification_results"]
    assert isinstance(vr, dict) and vr, "verification_results must have real content"
    assert "comp-foo" in vr
    result = vr["comp-foo"]
    assert result["a"] == 2
    assert result["z"] == 1

    rr = packet["residual_risk"]
    assert isinstance(rr, list) and rr, "residual_risk must have real content"
    for entry in rr:
        assert isinstance(entry, dict)
        assert isinstance(entry["component_id"], str) and entry["component_id"]
        assert isinstance(entry["message"], str) and entry["message"].strip()
    assert any(entry["component_id"] == "comp-foo" for entry in rr)

    ex = packet["exemption_changes"]
    assert "sealed" in ex
    assert "pinned_overrides" in ex
    assert ex["sealed"] == []
    assert ex["pinned_overrides"] == []


def test_changed_requirements_is_r_id_subset_with_space_separated_flags(repo, capsys):
    rc = run_main([
        "review-packet", "build", "--changed", "R-FOO-001",
        "--changed", "comp-foo", "--repo-root", str(repo), "--format", "json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    packet = json.loads(out)
    assert packet["changed_requirements"] == ["R-FOO-001"]


def test_usage_errors_return_2(repo, capsys):
    root = str(repo)
    cases = [
        ["review-packet", "build", "--repo-root=" + root],
        ["review-packet", "serve", "--changed=R-FOO-001"],
        ["review-packet"],
        ["review-packet", "build", "--repo-root=" + root, "--changed"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + root, "--format"],
    ]
    for argv in cases:
        rc = run_main(argv)
        capsys.readouterr()
        assert rc == 2, "expected exit 2 for argv %r, got %r" % (argv, rc)


def test_invalid_format_returns_2(repo, capsys):
    rc = run_main([
        "review-packet", "build", "--changed=R-FOO-001",
        "--repo-root=" + str(repo), "--format=bogus",
    ])
    capsys.readouterr()
    assert rc == 2


def test_check_readiness_value_error_returns_1(raising_repo, capsys):
    rc = run_main([
        "review-packet", "build", "--changed=R-FOO-001",
        "--repo-root=" + str(raising_repo),
    ])
    capsys.readouterr()
    assert rc == 1


def _section(text, heading):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    assert start is not None, "heading %r not found in output:\n%s" % (heading, text)
    body = []
    for line in lines[start:]:
        if line.startswith("## ") or line.startswith("# "):
            break
        body.append(line)
    return "\n".join(body)


def test_result_keys_sorted_in_json_and_markdown(repo, capsys):
    rc = run_main([
        "review-packet", "build", "--changed=R-FOO-001",
        "--repo-root=" + str(repo), "--format=json",
    ])
    json_out = capsys.readouterr().out
    assert rc == 0
    vr_idx = json_out.find('"verification_results"')
    assert vr_idx != -1
    tail = json_out[vr_idx:]
    a_idx = tail.find('"a"')
    z_idx = tail.find('"z"')
    assert a_idx != -1 and z_idx != -1
    assert a_idx < z_idx

    rc = run_main([
        "review-packet", "build", "--changed=R-FOO-001",
        "--repo-root=" + str(repo),
    ])
    md_out = capsys.readouterr().out
    assert rc == 0
    section = _section(md_out, "## Verification Results")
    comp_idx = section.find("comp-foo")
    assert comp_idx != -1, "comp-foo entry missing from Verification Results:\n%s" % section
    a_idx = section.find('"a"', comp_idx)
    z_idx = section.find('"z"', comp_idx)
    assert a_idx != -1 and z_idx != -1, section
    assert a_idx < z_idx