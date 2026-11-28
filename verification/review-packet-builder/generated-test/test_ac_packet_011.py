# hotdocs-criterion: sha256:fbf2f4d07dcc7a48053ed13fe0946fe51801ffd1aa1a6b895bf06bd7649e65da
import importlib.util
import subprocess
import sys
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {k: to_plain(v) for k, v in vars(value).items()}
    return value


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
            "adapter_sha256": "sha256:" + "ab" * 32,
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ],
    "drivers": [],
    "overall": "pass",
}

LICENSE_SCAN = {
    "scope": "full",
    "gate_version": "license_scanner@2.0.0",
    "blocked": True,
    "matches": [
        {
            "file": "gen/foo/foo.py",
            "license": "GPL-3.0-only",
            "similarity": 0.97,
        }
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
    "secret_scan": TOP_SECRET_SCAN,
    "not_ready_reasons": ["secret scan flagged 1 match"],
}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _tracker_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(VERIFY_REPORT) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return REPORT\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def _forbidden_source(module_name, log_path, names):
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        "MOD = " + repr(module_name) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "def _make(name):\n"
        "    def _f(*args, **kwargs):\n"
        "        _log(MOD + ':' + name)\n"
        "        raise RuntimeError(MOD + '.' + name + ' must not be called')\n"
        "    return _f\n"
        "\n"
        "def __getattr__(name):\n"
        "    if name.startswith('__'):\n"
        "        raise AttributeError(name)\n"
        "    return _make(name)\n"
        "\n"
    )
    for n in names:
        src += n + " = _make(" + repr(n) + ")\n"
    return src


def _build_fixture(repo_root, tracker_log, forbidden_log):
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
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
    _write(
        repo_root / "specs" / "capabilities" / "P-ZERO-EDIT.md",
        "---\n"
        "id: P-ZERO-EDIT\n"
        "title: Zero edit\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# P-ZERO-EDIT\n",
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        _tracker_source(tracker_log),
    )
    forbidden = {
        "verifier-orchestrator": ["verify", "verify_component", "run"],
        "license-scanner": ["scan", "scan_component", "scan_files", "scan_repository"],
        "secret-scanner": ["scan", "scan_files", "scan_repository", "scan_component"],
        "capability-scenario-verifier": [
            "run_capability_gates",
            "check_capability_provenance",
            "verify_capability",
            "run",
        ],
    }
    for slug, names in forbidden.items():
        module_name = slug.replace("-", "_")
        _write(
            repo_root / "gen" / slug / (module_name + ".py"),
            _forbidden_source(module_name, forbidden_log, names),
        )

    def git(*args):
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "initial")


def test_ac_packet_011_upstream_fields_read_from_verify_report(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    tracker_log = logs / "tracker.log"
    forbidden_log = logs / "forbidden.log"
    _build_fixture(repo_root, tracker_log, forbidden_log)

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    # The provenance-tracker stand-in was consulted.
    assert tracker_log.is_file()
    assert "check_readiness" in tracker_log.read_text().splitlines()

    # No live call into any of the four upstream components.
    calls = forbidden_log.read_text().splitlines() if forbidden_log.is_file() else []
    assert calls == [], calls

    # verification_results from VerifyReport.components[...].verification_report
    verification_results = to_plain(field(packet, "verification_results"))
    assert verification_results == {"comp-foo": VERIFICATION_REPORT}

    # provenance_hit_status from VerifyReport.components[...].hit
    hit_status = to_plain(field(packet, "provenance_hit_status"))
    assert hit_status == {"comp-foo": True}

    # capability_scenarios from VerifyReport.capabilities[...].capability_scenario_report
    capability_scenarios = to_plain(field(packet, "capability_scenarios"))
    assert capability_scenarios == {"P-ZERO-EDIT": CAPABILITY_SCENARIO_REPORT}

    # compliance_flags from VerifyReport license/secret scan values
    compliance = field(packet, "compliance_flags")
    license_entries = to_plain(field(compliance, "license_scan"))
    secret_entries = to_plain(field(compliance, "secret_scan"))

    assert isinstance(license_entries, list)
    assert {"component_id": "comp-foo", "result": LICENSE_SCAN} in license_entries
    for entry in license_entries:
        assert entry["result"] == LICENSE_SCAN

    assert isinstance(secret_entries, list)
    assert len(secret_entries) >= 1
    assert any(entry["result"] == TOP_SECRET_SCAN for entry in secret_entries)
    for entry in secret_entries:
        assert "component_id" in entry
        assert entry["result"] in (TOP_SECRET_SCAN, COMPONENT_SECRET_SCAN)