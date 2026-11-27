# hotdocs-criterion: sha256:2f418be12420b358e04d5606551585d4627e27da3eaa03dc2596d88368bedb32
import copy
import dataclasses
import json
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if hasattr(value, "__dict__") and not isinstance(value, (str, int, float, bool)):
        return {k: to_plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    "drivers": [],
    "overall": "pass",
}

LICENSE_SCAN_RESULT = {
    "scope": "full",
    "gate_version": "license_scanner@1.0.0",
    "blocked": True,
    "flagged": True,
    "matches": [
        {"file": "gen/foo/foo.py", "license": "GPL-3.0", "similarity": 0.97}
    ],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
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
    "cache_hit": False,
}

TOP_SECRET_SCAN = {
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

CAPABILITY_SCENARIO_REPORT = {"P-ZERO-EDIT": {"overall": "pass", "scenarios": []}}

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": False,
    "components": {
        "comp-foo": {
            "hit": True,
            "reason": None,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": LICENSE_SCAN_RESULT,
            "secret_scan": COMPONENT_SECRET_SCAN,
        }
    },
    "capabilities": {
        "P-ZERO-EDIT": {
            "hit": True,
            "capability_scenario_report": CAPABILITY_SCENARIO_REPORT,
        }
    },
    "secret_scan": TOP_SECRET_SCAN,
    "not_ready_reasons": ["secret scan flagged 1 match"],
}

FORBIDDEN = [
    ("verifier-orchestrator", "verifier_orchestrator"),
    ("license-scanner", "license_scanner"),
    ("secret-scanner", "secret_scanner"),
    ("capability-scenario-verifier", "capability_scenario_verifier"),
    ("provenance-checker", "provenance_checker"),
]


def _build_fixture(repo_root, tracker_log, forbidden_log):
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )

    tracker_src = (
        "LOG = " + repr(str(tracker_log)) + "\n"
        "REPORT = " + repr(copy.deepcopy(VERIFY_REPORT)) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('check_readiness\\n')\n"
        "    import copy as _copy\n"
        "    return _copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", tracker_src)

    for slug, module_name in FORBIDDEN:
        src = (
            "LOG = " + repr(str(forbidden_log)) + "\n"
            "MODNAME = " + repr(module_name) + "\n"
            "\n"
            "def __getattr__(name):\n"
            "    if name.startswith('__'):\n"
            "        raise AttributeError(name)\n"
            "    def _forbidden(*args, **kwargs):\n"
            "        with open(LOG, 'a') as f:\n"
            "            f.write(MODNAME + ':' + name + '\\n')\n"
            "        raise RuntimeError('live call into ' + MODNAME + '.' + name + ' is forbidden')\n"
            "    return _forbidden\n"
        )
        _write(repo_root / "gen" / slug / (module_name + ".py"), src)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")


def test_ac_packet_011_fields_read_only_from_verify_report(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    tracker_log = logs / "tracker.log"
    forbidden_log = logs / "forbidden.log"
    _build_fixture(repo_root, tracker_log, forbidden_log)

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    # The data came via provenance-tracker's check_readiness.
    assert tracker_log.is_file(), "provenance-tracker check_readiness was never called"
    assert "check_readiness" in tracker_log.read_text().splitlines()

    # No live call into any of the upstream components.
    forbidden_calls = forbidden_log.read_text().splitlines() if forbidden_log.exists() else []
    assert forbidden_calls == [], "unexpected live calls: " + repr(forbidden_calls)

    # verification_results
    verification_results = to_plain(field(packet, "verification_results"))
    assert verification_results == {"comp-foo": VERIFICATION_REPORT}

    # provenance_hit_status
    hit_status = to_plain(field(packet, "provenance_hit_status"))
    assert hit_status == {"comp-foo": True}

    # capability_scenarios: keyed by P-id, value the report exactly as read (not unwrapped)
    capability_scenarios = to_plain(field(packet, "capability_scenarios"))
    assert capability_scenarios == {"P-ZERO-EDIT": CAPABILITY_SCENARIO_REPORT}

    # compliance_flags
    compliance_flags = field(packet, "compliance_flags")
    license_entries = to_plain(field(compliance_flags, "license_scan"))
    secret_entries = to_plain(field(compliance_flags, "secret_scan"))

    assert isinstance(license_entries, list)
    assert {"component_id": "comp-foo", "result": LICENSE_SCAN_RESULT} in license_entries
    for entry in license_entries:
        assert set(entry.keys()) >= {"component_id", "result"}

    assert isinstance(secret_entries, list)
    assert secret_entries, "flagged top-level secret_scan missing from compliance_flags.secret_scan"
    for entry in secret_entries:
        assert set(entry.keys()) >= {"component_id", "result"}
    assert any(entry["result"] == TOP_SECRET_SCAN for entry in secret_entries), (
        "top-level secret_scan result not carried verbatim: " + json.dumps(secret_entries)
    )