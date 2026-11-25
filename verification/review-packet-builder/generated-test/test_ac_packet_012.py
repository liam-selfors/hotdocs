# hotdocs-criterion: sha256:8cf902a245932c938210f1315ef85f0f7ceccee7d394f45ba41388dab1838903
import json
import subprocess
from pathlib import Path

import pytest

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _init_repo(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q")
    (repo_root / "README.md").write_text("fixture repo\n")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")


def _verification_report():
    # Deliberately insert "z" before "a" so sorted output is observable.
    report = {}
    report["z"] = 1
    report["a"] = 2
    report["component_id"] = "comp-foo"
    report["criteria"] = []
    report["requirement_results"] = {}
    report["interface_drift"] = False
    report["mutation_score"] = 0.5
    report["mutation_error"] = None
    report["assets"] = []
    report["overall"] = "pass"
    return report


def _secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(),
                "license_scan": {"blocked": False},
                "secret_scan": _secret_scan(),
            }
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [],
    }


def _write_fake_tracker(repo_root, log_path, raise_message=None):
    base = repo_root / "gen" / "provenance-tracker"
    base.mkdir(parents=True, exist_ok=True)
    src = ""
    src += "def _log(line):\n"
    src += "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
    src += "        fh.write(line + '\\n')\n"
    src += "\n"
    src += "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    src += "    _log('check_readiness')\n"
    if raise_message is not None:
        src += "    raise ValueError(" + repr(raise_message) + ")\n"
    else:
        src += "    return " + repr(_verify_report()) + "\n"
    src += "\n"
    src += "def last_requirement_failures(component_id, repo_root):\n"
    src += "    _log('last_requirement_failures')\n"
    src += "    return []\n"
    (base / "provenance_tracker.py").write_text(src)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add provenance-tracker stand-in")


@pytest.fixture
def good_repo(tmp_path):
    repo_root = tmp_path / "good_repo"
    log_path = tmp_path / "good_calls.log"
    _init_repo(repo_root)
    _write_fake_tracker(repo_root, log_path)
    return repo_root, log_path


@pytest.fixture
def raising_repo(tmp_path):
    repo_root = tmp_path / "raising_repo"
    log_path = tmp_path / "raising_calls.log"
    _init_repo(repo_root)
    _write_fake_tracker(repo_root, log_path, raise_message="P-FOO needs a fresh run: pass --model")
    return repo_root, log_path


def _section(markdown, heading):
    lines = markdown.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    assert start is not None, "missing heading " + heading + " in:\n" + markdown
    out = []
    for line in lines[start:]:
        if line.startswith("## ") or line.startswith("# "):
            break
        out.append(line)
    return "\n".join(out)


def test_json_build_succeeds_with_real_content(good_repo, capsys):
    repo_root, log_path = good_repo
    rc = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root), "--format=json"]
    )
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert log_path.is_file() and "check_readiness" in log_path.read_text()

    packet = json.loads(captured.out)
    assert captured.out.strip() == json.dumps(packet, indent=2, sort_keys=True).strip()

    vr = field(packet, "verification_results")
    assert isinstance(vr, dict) and vr
    assert "comp-foo" in vr
    assert vr["comp-foo"]["a"] == 2
    assert vr["comp-foo"]["z"] == 1

    rr = field(packet, "residual_risk")
    assert isinstance(rr, list) and rr
    for entry in rr:
        assert isinstance(entry, dict)
        assert isinstance(entry["component_id"], str) and entry["component_id"]
        assert isinstance(entry["message"], str) and entry["message"]

    ex = field(packet, "exemption_changes")
    assert "sealed" in ex and "pinned_overrides" in ex
    assert isinstance(ex["sealed"], list)
    assert isinstance(ex["pinned_overrides"], list)


def test_changed_space_separated_and_repeated(good_repo, capsys):
    repo_root, _ = good_repo
    rc = review_packet_builder.main(
        ["review-packet", "build", "--changed", "R-FOO-001",
         "--changed", "comp-foo", "--repo-root", str(repo_root),
         "--format", "json"]
    )
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    packet = json.loads(captured.out)
    assert field(packet, "changed_requirements") == ["R-FOO-001"]


def test_usage_errors_return_2(good_repo, capsys):
    repo_root, _ = good_repo
    argvs = [
        ["review-packet", "build", "--repo-root=" + str(repo_root)],
        ["review-packet", "serve", "--changed=R-FOO-001"],
        ["review-packet"],
        ["review-packet", "build", "--repo-root=" + str(repo_root), "--changed"],
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root"],
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root), "--format"],
    ]
    for argv in argvs:
        rc = review_packet_builder.main(argv)
        capsys.readouterr()
        assert rc == 2, argv


def test_invalid_format_returns_2(good_repo, capsys):
    repo_root, _ = good_repo
    rc = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root), "--format=bogus"]
    )
    capsys.readouterr()
    assert rc == 2


def test_check_readiness_value_error_returns_1(raising_repo, capsys):
    repo_root, log_path = raising_repo
    rc = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root)]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert log_path.is_file() and "check_readiness" in log_path.read_text()
    assert "P-FOO needs a fresh run" in (captured.out + captured.err)


def test_keys_sorted_in_json_and_markdown(good_repo, capsys):
    repo_root, _ = good_repo

    rc = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root), "--format=json"]
    )
    out_json = capsys.readouterr().out
    assert rc == 0
    ia = out_json.find('"a"')
    iz = out_json.find('"z"')
    assert ia != -1 and iz != -1
    assert ia < iz

    rc = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001",
         "--repo-root=" + str(repo_root)]
    )
    out_md = capsys.readouterr().out
    assert rc == 0
    section = _section(out_md, "## Verification Results")
    line = next(
        (l for l in section.splitlines() if l.strip().startswith("- comp-foo")),
        None,
    )
    assert line is not None, section
    ia = line.find('"a"')
    iz = line.find('"z"')
    assert ia != -1 and iz != -1, line
    assert ia < iz