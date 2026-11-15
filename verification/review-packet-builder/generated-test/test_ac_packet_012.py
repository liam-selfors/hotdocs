import json
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


VERIFICATION_REPORT = {
    "z": 1,
    "a": 2,
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.92,
    "overall": "pass",
}

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": True,
    "components": {
        "comp-foo": {
            "hit": True,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": {"blocked": False, "findings": []},
            "secret_scan": {"flagged": False, "findings": []},
        }
    },
    "capabilities": {},
    "not_ready_reasons": [],
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=fixture",
            "-c", "user.email=fixture@example.com",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _make_repo(base: Path, raise_usage: bool = False):
    repo = base / "repo"
    fake_dir = repo / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    log_path = base / "provenance_tracker_invocations.log"

    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "RAISE_USAGE = " + repr(bool(raise_usage)) + "\n"
        "\n"
        "\n"
        "class UsageError(Exception):\n"
        "    pass\n"
        "\n"
        "\n"
        "def _log(name):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    if RAISE_USAGE:\n"
        "        raise UsageError('fixture: provenance-tracker usage error')\n"
        "    return " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source)
    (repo / "README.md").write_text("fixture repo\n")

    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial fixture commit")
    return repo, log_path


def run_main(argv, capsys):
    capsys.readouterr()
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
    out = capsys.readouterr().out
    return rc, out


@pytest.fixture
def good_repo(tmp_path):
    return _make_repo(tmp_path)


def test_json_build_renders_real_content(good_repo, capsys):
    repo, log_path = good_repo
    rc, out = run_main(
        [
            "review-packet", "build", "--changed=R-FOO-001",
            "--repo-root=" + str(repo), "--format=json",
        ],
        capsys,
    )
    assert rc == 0
    assert log_path.exists() and "check_readiness" in log_path.read_text()

    packet = json.loads(out)

    vr = field(packet, "verification_results")
    assert isinstance(vr, dict) and vr, "verification_results must have real content"
    assert "comp-foo" in vr
    report = vr["comp-foo"]
    assert report["a"] == 2
    assert report["z"] == 1
    assert report["overall"] == "pass"
    assert report["mutation_score"] == 0.92

    risk = field(packet, "residual_risk")
    assert isinstance(risk, list) and risk, "residual_risk must have real content"
    for entry in risk:
        assert isinstance(entry, dict)
        assert "component_id" in entry and "message" in entry
        assert isinstance(entry["message"], str) and entry["message"].strip()
    assert any(entry["component_id"] == "comp-foo" for entry in risk)

    ex = field(packet, "exemption_changes")
    assert "sealed" in ex
    assert "pinned_overrides" in ex
    assert isinstance(ex["sealed"], list)
    assert isinstance(ex["pinned_overrides"], list)


def test_space_separated_repeated_changed_flag(good_repo, capsys):
    repo, _ = good_repo
    rc, out = run_main(
        [
            "review-packet", "build",
            "--changed", "R-FOO-001",
            "--changed", "comp-foo",
            "--repo-root", str(repo),
            "--format", "json",
        ],
        capsys,
    )
    assert rc == 0
    packet = json.loads(out)
    assert field(packet, "changed_requirements") == ["R-FOO-001"]


@pytest.mark.parametrize(
    "argv_template",
    [
        ["review-packet", "build", "--repo-root={repo}"],
        ["review-packet", "serve", "--changed=R-FOO-001"],
        ["review-packet"],
        ["review-packet", "build", "--repo-root={repo}", "--changed"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root={repo}", "--format"],
    ],
)
def test_usage_errors_return_2(good_repo, capsys, argv_template):
    repo, _ = good_repo
    argv = [a.replace("{repo}", str(repo)) for a in argv_template]
    rc, _ = run_main(argv, capsys)
    assert rc == 2


def test_invalid_format_returns_2(good_repo, capsys):
    repo, _ = good_repo
    rc, _ = run_main(
        [
            "review-packet", "build", "--changed=R-FOO-001",
            "--repo-root=" + str(repo), "--format=bogus",
        ],
        capsys,
    )
    assert rc == 2


def test_upstream_usage_error_returns_1(tmp_path, capsys):
    repo, _ = _make_repo(tmp_path, raise_usage=True)
    rc, _ = run_main(
        [
            "review-packet", "build", "--changed=R-FOO-001",
            "--repo-root=" + str(repo),
        ],
        capsys,
    )
    assert rc == 1


def test_sorted_keys_in_json_and_markdown(good_repo, capsys):
    repo, _ = good_repo

    rc, out = run_main(
        [
            "review-packet", "build", "--changed=R-FOO-001",
            "--repo-root=" + str(repo), "--format=json",
        ],
        capsys,
    )
    assert rc == 0
    packet = json.loads(out)
    assert out.strip() == json.dumps(packet, indent=2, sort_keys=True)
    assert '"a"' in out and '"z"' in out
    assert out.index('"a"') < out.index('"z"')

    rc, md = run_main(
        [
            "review-packet", "build", "--changed=R-FOO-001",
            "--repo-root=" + str(repo),
        ],
        capsys,
    )
    assert rc == 0
    heading = "## Verification Results"
    assert heading in md
    rest = md[md.index(heading) + len(heading):]
    end = rest.find("\n## ")
    section = rest if end == -1 else rest[:end]
    assert "comp-foo" in section
    assert '"a"' in section and '"z"' in section
    assert section.index('"a"') < section.index('"z"')