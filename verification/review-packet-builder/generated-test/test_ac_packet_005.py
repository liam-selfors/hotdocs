# hotdocs-criterion: sha256:41d8dedb7f24c27fcd738b91c2d7c4118466def4acb10008d31760be13722d94
"""AC-PACKET-005: compliance_flags is its own explicit section.

Covers R-PACKET-005.
"""

import copy
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def as_plain(value):
    """Normalise a compliance entry (dict or object) into a plain dict."""
    return {
        "component_id": field(value, "component_id"),
        "result": field(value, "result"),
    }


def clean_secret_scan():
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


def flagged_secret_scan():
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": True,
        "matches": [
            {
                "file": "a/b.py",
                "line": 3,
                "rule_id": "AWS Access Key",
                "risk_tier": "high",
            }
        ],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def clean_license_scan():
    return {
        "blocked": False,
        "matches": [],
        "gate_version": "license_scanner@1.0.0",
        "cache_hit": False,
    }


def verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "llm-judge",
                "result": "pass",
                "rationale": "ok",
            }
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
    }


def component_result(secret_scan):
    return {
        "hit": True,
        "reason": None,
        "verification_report": verification_report(),
        "license_scan": clean_license_scan(),
        "secret_scan": secret_scan,
    }


def verify_report(component_secret_scan, repo_secret_scan):
    return {
        "scope": "blast-radius",
        "ready": not repo_secret_scan["flagged"],
        "components": {"comp-foo": component_result(component_secret_scan)},
        "capabilities": {},
        "secret_scan": repo_secret_scan,
        "not_ready_reasons": [] if not repo_secret_scan["flagged"]
        else ["secret scan flagged"],
    }


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def build_fixture(tmp_path, report):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a fixture term.\n",
    )
    comp_dir = repo_root / "specs" / "components" / "foo"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do bar.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: llm-judge\n\nFoo does bar.\n",
    )
    write(comp_dir / "interface" / "library.md", "# Library\n\n```\nfoo() -> None\n```\n")
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "legacy" / "foo" / "foo.py", "def foo():\n    return None\n")

    tracker_src = (
        "import json\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0,\n"
        "                    llm_backend=None):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        tracker_src,
    )

    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")
    return repo_root, log_path


def run_builder(tmp_path, report):
    repo_root, log_path = build_fixture(tmp_path, report)
    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], repo_root
    )
    assert log_path.is_file(), "the provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text()
    assert has_field(packet, "compliance_flags")
    flags = field(packet, "compliance_flags")
    assert flags is not None
    return flags


def test_clean_scans_give_explicit_empty_compliance_flags(tmp_path):
    report = verify_report(clean_secret_scan(), clean_secret_scan())
    flags = run_builder(tmp_path, report)

    assert has_field(flags, "license_scan"), "license_scan omitted"
    assert has_field(flags, "secret_scan"), "secret_scan omitted"
    license_scan = field(flags, "license_scan")
    secret_scan = field(flags, "secret_scan")
    assert license_scan is not None
    assert secret_scan is not None
    assert list(license_scan) == []
    assert list(secret_scan) == []


def test_component_stored_secret_scan_is_never_read(tmp_path):
    report = verify_report(flagged_secret_scan(), clean_secret_scan())
    report["secret_scan"] = {
        **clean_secret_scan(),
        "flagged": False,
        "matches": [],
    }
    flags = run_builder(tmp_path, report)

    assert has_field(flags, "secret_scan")
    secret_scan = field(flags, "secret_scan")
    assert secret_scan is not None
    assert list(secret_scan) == []


def test_flagged_repository_scan_is_one_null_component_entry(tmp_path):
    s = flagged_secret_scan()
    report = verify_report(clean_secret_scan(), copy.deepcopy(s))
    flags = run_builder(tmp_path, report)

    assert has_field(flags, "secret_scan")
    secret_scan = list(field(flags, "secret_scan"))
    assert len(secret_scan) == 1
    entries = [as_plain(e) for e in secret_scan]
    assert entries == [{"component_id": None, "result": s}]