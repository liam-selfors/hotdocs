# hotdocs-criterion: sha256:85fc729a1241602e54a94add4e752153beef6cad21484778bc2068ec575d697c
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 1.0,
    "mutation_error": None,
    "assets": [
        {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": "sha256:abc123",
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ],
    "overall": "pass",
}

LICENSE_SCAN = {
    "blocked": True,
    "gate_version": "license_scanner@1.0.0",
    "matches": [{"file": "gen/foo/foo.py", "license": "GPL-3.0", "similarity": 0.97}],
    "marker_unique_tag": "lic-marker-7731",
}

COMPONENT_SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": True,
}

REPO_SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": True,
    "matches": [
        {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "gen/foo/config.py", "line": 12}
    ],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

CAPABILITY_SCENARIO_REPORT = {
    "P-ZERO-EDIT": {
        "overall": "pass",
        "scenarios": [{"id": "SC-ZERO-EDIT-001", "result": "pass", "marker": "cap-marker-4412"}],
    }
}

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": False,
    "components": {
        "comp-foo": {
            "hit": True,
            "reason": None,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": LICENSE_SCAN,
            "secret_scan": COMPONENT_SECRET_SCAN,
        }
    },
    "capabilities": {
        "P-ZERO-EDIT": {
            "hit": True,
            "capability_scenario_report": CAPABILITY_SCENARIO_REPORT,
        }
    },
    "secret_scan": REPO_SECRET_SCAN,
    "not_ready_reasons": ["comp-foo: license scan blocked"],
}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _forbidden_module_source(slug, log_path):
    return (
        "def __getattr__(name):\n"
        "    if name.startswith('__'):\n"
        "        raise AttributeError(name)\n"
        "    def _called(*args, **kwargs):\n"
        "        with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "            fh.write(" + repr(slug) + " + ':' + name + '\\n')\n"
        "        raise RuntimeError(" + repr(slug + " must not be called") + ")\n"
        "    return _called\n"
    )


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    tracker_log = tmp_path / "tracker_calls.log"
    forbidden_log = tmp_path / "forbidden_calls.log"

    # Minimal spec corpus for comp-foo realizing P-ZERO-EDIT.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "---\n\n# Foo\n\nA fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do the thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )

    tracker_src = (
        "VERIFY_REPORT = " + repr(VERIFY_REPORT) + "\n\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(" + repr(str(tracker_log)) + ", 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return VERIFY_REPORT\n\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", tracker_src)

    for slug in (
        "verifier-orchestrator",
        "license-scanner",
        "secret-scanner",
        "capability-scenario-verifier",
        "provenance-checker",
    ):
        module_name = slug.replace("-", "_")
        _write(
            repo_root / "gen" / slug / (module_name + ".py"),
            _forbidden_module_source(slug, forbidden_log),
        )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")
    return repo_root, tracker_log, forbidden_log


def test_ac_packet_011_fields_read_only_from_verify_report(tmp_path):
    repo_root, tracker_log, forbidden_log = _build_repo(tmp_path)

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    # provenance-tracker's check_readiness was the read source.
    assert tracker_log.is_file()
    assert "check_readiness" in tracker_log.read_text().splitlines()

    # No live call into any of the underlying components.
    calls = forbidden_log.read_text() if forbidden_log.is_file() else ""
    assert calls == "", "unexpected live dependency calls: " + calls

    verification_results = field(packet, "verification_results")
    assert "comp-foo" in verification_results
    assert verification_results["comp-foo"] == VERIFICATION_REPORT

    provenance_hit_status = field(packet, "provenance_hit_status")
    assert provenance_hit_status["comp-foo"] is True

    compliance_flags = field(packet, "compliance_flags")
    license_entries = field(compliance_flags, "license_scan")
    assert len(license_entries) == 1
    entry = license_entries[0]
    assert field(entry, "component_id") == "comp-foo"
    assert field(entry, "result") == LICENSE_SCAN

    secret_entries = field(compliance_flags, "secret_scan")
    assert len(secret_entries) == 1
    assert field(secret_entries[0], "component_id") is None
    assert field(secret_entries[0], "result") == REPO_SECRET_SCAN

    capability_scenarios = field(packet, "capability_scenarios")
    assert set(capability_scenarios.keys()) == {"P-ZERO-EDIT"}
    assert capability_scenarios["P-ZERO-EDIT"] == CAPABILITY_SCENARIO_REPORT

    # Capability section is distinct from verification_results.
    assert "P-ZERO-EDIT" not in verification_results