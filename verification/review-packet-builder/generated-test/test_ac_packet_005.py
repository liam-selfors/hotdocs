# hotdocs-criterion: sha256:26bf8c926229268ff272012e996d9d9bf56262b3e943e6ea2fabba0eacd21629
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _secret_scan(flagged, matches):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": flagged,
        "matches": matches,
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _license_scan(blocked):
    return {"blocked": blocked, "findings": []}


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }


def _component_result(component_secret_flagged):
    if component_secret_flagged:
        stored_secret = _secret_scan(
            True,
            [{"rule_id": "AWS Access Key", "risk_tier": "high", "file": "legacy/foo/x.py", "line": 7}],
        )
    else:
        stored_secret = _secret_scan(False, [])
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(),
        "license_scan": _license_scan(False),
        "secret_scan": stored_secret,
    }


def _build_repo(repo_root, report, log_path):
    repo_root.mkdir(parents=True, exist_ok=True)

    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)
    (comp_dir / "interface").mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n"
    )
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do foo.\n"
    )
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen foo runs\nThen foo happens\n```\n"
    )
    (comp_dir / "interface" / "library.md").write_text("# Library\n\n```\nfoo() -> None\n```\n")
    (comp_dir / "constraints.md").write_text("# Constraints\n\nNone.\n")
    (repo_root / "legacy" / "foo").mkdir(parents=True)
    (repo_root / "legacy" / "foo" / "foo.py").write_text("def foo():\n    return None\n")

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    source = (
        "from pathlib import Path\n"
        "\n"
        "REPORT = " + repr(report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )
    (tracker_dir / "provenance_tracker.py").write_text(source)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")


def _report(secret_scan, component_secret_flagged):
    return {
        "scope": "blast-radius",
        "ready": not bool(secret_scan and secret_scan.get("flagged")),
        "components": {"comp-foo": _component_result(component_secret_flagged)},
        "capabilities": {},
        "secret_scan": secret_scan,
        "not_ready_reasons": [],
    }


def _run(tmp_path, report):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "tracker.log"
    _build_repo(repo_root, report, log_path)
    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)
    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text().splitlines()
    return packet


def test_clean_scans_give_explicit_empty_compliance_flags(tmp_path):
    packet = _run(tmp_path, _report(_secret_scan(False, []), False))
    assert has_field(packet, "compliance_flags")
    flags = field(packet, "compliance_flags")
    assert flags is not None
    assert has_field(flags, "license_scan")
    assert has_field(flags, "secret_scan")
    assert list(field(flags, "license_scan")) == []
    assert list(field(flags, "secret_scan")) == []


def test_component_stored_secret_scan_is_never_read(tmp_path):
    packet = _run(tmp_path, _report(_secret_scan(False, []), True))
    flags = field(packet, "compliance_flags")
    assert has_field(flags, "secret_scan")
    assert list(field(flags, "secret_scan")) == []


def test_flagged_repository_secret_scan_is_single_null_component_entry(tmp_path):
    s = _secret_scan(
        True,
        [{"file": "a/b.py", "line": 3, "rule_id": "AWS Access Key", "risk_tier": "high"}],
    )
    packet = _run(tmp_path, _report(s, False))
    flags = field(packet, "compliance_flags")
    secret = list(field(flags, "secret_scan"))
    assert len(secret) == 1
    entry = secret[0]
    assert field(entry, "component_id") is None
    assert field(entry, "result") == s
    if isinstance(entry, dict):
        assert entry == {"component_id": None, "result": s}