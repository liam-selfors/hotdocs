# hotdocs-criterion: sha256:b6c64e3db5c043593531e6542768e90e8a177a5a635d83e6311c9bbe567f0233
"""AC-PACKET-011: every upstream-sourced packet field is read from
provenance-tracker's check_readiness VerifyReport, never from a live call
into verifier-orchestrator, license-scanner, secret-scanner,
capability-scenario-verifier, or provenance-checker."""

import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VERIFICATION_REPORT = {
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
    "mutation_score": 1.0,
    "mutation_error": None,
    "overall": "pass",
}

LICENSE_SCAN = {
    "blocked": True,
    "findings": [{"path": "foo.py", "license": "GPL-3.0", "similarity": 0.97}],
}

SECRET_SCAN = {
    "flagged": True,
    "findings": [{"path": "foo.py", "line": 3, "kind": "aws-access-key"}],
}

CAPABILITY_SCENARIO_REPORT = {
    "P-ZERO-EDIT": {
        "overall": "pass",
        "scenarios": [{"id": "SC-ZERO-EDIT-001", "result": "pass"}],
    }
}

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": False,
    "components": {
        "comp-foo": {
            "hit": True,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": LICENSE_SCAN,
            "secret_scan": SECRET_SCAN,
        }
    },
    "capabilities": {
        "P-ZERO-EDIT": {
            "hit": True,
            "capability_scenario_report": CAPABILITY_SCENARIO_REPORT,
        }
    },
    "not_ready_reasons": [
        "comp-foo: license scan blocked",
        "comp-foo: secret scan flagged",
    ],
}

FORBIDDEN_SLUGS = [
    "verifier-orchestrator",
    "license-scanner",
    "secret-scanner",
    "capability-scenario-verifier",
    "provenance-checker",
]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com"]
        + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _tracker_source(log_path):
    return (
        "from pathlib import Path\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write('check_readiness ' + repr(changed_ids) + '\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def _forbidden_source(slug, log_path):
    return (
        "_LOG = " + repr(str(log_path)) + "\n"
        "_SLUG = " + repr(slug) + "\n"
        "\n"
        "\n"
        "def _record(name):\n"
        "    with open(_LOG, 'a') as fh:\n"
        "        fh.write(_SLUG + ' ' + name + '\\n')\n"
        "\n"
        "\n"
        "def __getattr__(name):\n"
        "    if name.startswith('__'):\n"
        "        raise AttributeError(name)\n"
        "\n"
        "    def _forbidden(*args, **kwargs):\n"
        "        _record(name)\n"
        "        raise RuntimeError('live call into ' + _SLUG + '.' + name + ' is forbidden')\n"
        "\n"
        "    return _forbidden\n"
    )


def _build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    repo_root.mkdir()

    tracker_log = log_dir / "tracker.log"
    forbidden_log = log_dir / "forbidden.log"

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\nFoo does the thing.\n",
    )

    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        _tracker_source(tracker_log),
    )
    for slug in FORBIDDEN_SLUGS:
        module_name = slug.replace("-", "_")
        _write(
            repo_root / "gen" / slug / (module_name + ".py"),
            _forbidden_source(slug, forbidden_log),
        )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial fixture")

    # A spec change in the working tree for the packet's diff to describe.
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the thing, quickly.\n",
    )

    return repo_root, tracker_log, forbidden_log


def test_upstream_fields_come_only_from_verify_report(tmp_path):
    repo_root, tracker_log, forbidden_log = _build_fixture(tmp_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], repo_root
    )

    # provenance-tracker's check_readiness was actually consulted.
    assert tracker_log.is_file(), "check_readiness was never called"
    assert "check_readiness" in tracker_log.read_text()

    # No live call into any of the components the VerifyReport already covers.
    calls = forbidden_log.read_text() if forbidden_log.is_file() else ""
    assert calls == "", "unexpected live upstream calls:\n" + calls

    # verification_results: verbatim from components[comp-foo].verification_report
    verification_results = field(packet, "verification_results")
    assert verification_results["comp-foo"] == VERIFICATION_REPORT

    # compliance_flags: from license_scan / secret_scan in the VerifyReport
    compliance_flags = field(packet, "compliance_flags")
    license_entries = field(compliance_flags, "license_scan")
    secret_entries = field(compliance_flags, "secret_scan")
    assert len(license_entries) == 1
    assert field(license_entries[0], "component_id") == "comp-foo"
    assert field(license_entries[0], "result") == LICENSE_SCAN
    assert len(secret_entries) == 1
    assert field(secret_entries[0], "component_id") == "comp-foo"
    assert field(secret_entries[0], "result") == SECRET_SCAN

    # provenance_hit_status: from the VerifyReport's own `hit` field
    provenance_hit_status = field(packet, "provenance_hit_status")
    assert provenance_hit_status == {"comp-foo": True}

    # capability_scenarios: from capabilities[P-ZERO-EDIT].capability_scenario_report,
    # keyed by P-id, value exactly as read (itself keyed by P-id, never unwrapped)
    capability_scenarios = field(packet, "capability_scenarios")
    assert capability_scenarios == {"P-ZERO-EDIT": CAPABILITY_SCENARIO_REPORT}