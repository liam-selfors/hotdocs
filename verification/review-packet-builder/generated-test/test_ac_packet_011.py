import review_packet_builder

import dataclasses
import json
import os
import subprocess
from pathlib import Path

import pytest


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def to_plain(value):
    """Normalize a returned value (dict, dataclass, or plain object) to plain
    JSON-like Python data, so it can be compared against the fixture dicts."""
    if isinstance(value, dict):
        return {k: to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(v) for v in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_plain(dataclasses.asdict(value))
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {k: to_plain(v) for k, v in vars(value).items() if not k.startswith("_")}
    return value


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


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------
# Fixture data: what provenance-tracker's check_readiness reports
# --------------------------------------------------------------------------

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "pass"},
    "interface_drift": False,
    "mutation_score": 1.0,
    "overall": "pass",
    "marker": "from-verify-report-verification-7731",
}

LICENSE_SCAN = {
    "blocked": True,
    "findings": [{"path": "foo.py", "license": "GPL-3.0", "marker": "from-verify-report-license-4417"}],
}

SECRET_SCAN = {
    "flagged": True,
    "findings": [{"path": "foo.py", "line": 3, "marker": "from-verify-report-secret-9902"}],
}

CAPABILITY_SCENARIO_REPORT = {
    "P-ZERO-EDIT": {
        "overall": "pass",
        "scenarios": [{"id": "S-ZERO-EDIT-001", "result": "pass", "marker": "from-verify-report-cap-5560"}],
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


TRACKER_TEMPLATE = '''\
import json as _json

_LOG_PATH = {log_path!r}
_REPORT = {report}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(record) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{"module": "provenance_tracker", "fn": "check_readiness",
           "changed_ids": repr(changed_ids)}})
    return {report}


def last_requirement_failures(component_id, repo_root):
    _log({{"module": "provenance_tracker", "fn": "last_requirement_failures",
           "component_id": repr(component_id)}})
    return []
'''


FORBIDDEN_TEMPLATE = '''\
import json as _json

_LOG_PATH = {log_path!r}
_MODULE = {module_name!r}


def _log(fn):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps({{"module": _MODULE, "fn": fn}}) + "\\n")


def _make(fn_name):
    def _fake(*args, **kwargs):
        _log(fn_name)
        return None
    _fake.__name__ = fn_name
    return _fake


{explicit}


def __getattr__(name):
    if name.startswith("_"):
        raise AttributeError(name)
    return _make(name)
'''

FORBIDDEN_MODULES = {
    "verifier-orchestrator": ("verifier_orchestrator", ["verify", "run_verification", "verify_component"]),
    "license-scanner": ("license_scanner", ["scan", "scan_licenses", "license_scan"]),
    "secret-scanner": ("secret_scanner", ["scan", "scan_secrets", "secret_scan"]),
    "capability-scenario-verifier": (
        "capability_scenario_verifier",
        ["check_capability_provenance", "run_capability_gates"],
    ),
    "provenance-checker": (
        "provenance_checker",
        ["current_sealed_key", "current_provenance_key", "check_provenance", "check_sealed_provenance"],
    ),
}


@pytest.fixture
def repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.log"
    log_path.write_text("", encoding="utf-8")

    # Minimal spec corpus for comp-foo, realizing P-ZERO-EDIT.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do one thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-002.md",
        "**R-FOO-002** — Foo MUST do another thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "constraints.md",
        "# Constraints\n\nNone.\n",
    )

    # provenance-tracker stand-in.
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        TRACKER_TEMPLATE.format(log_path=str(log_path), report=repr(VERIFY_REPORT)),
    )

    # Fakes for every component the packet must NOT call directly.
    for slug, (module_name, fns) in FORBIDDEN_MODULES.items():
        explicit = "\n".join(f"{fn} = _make({fn!r})" for fn in fns)
        _write(
            repo_root / "gen" / slug / f"{module_name}.py",
            FORBIDDEN_TEMPLATE.format(
                log_path=str(log_path), module_name=module_name, explicit=explicit
            ),
        )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial fixture commit")

    return repo_root, log_path


def _read_log(log_path):
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


# --------------------------------------------------------------------------
# AC-PACKET-011
# --------------------------------------------------------------------------

def test_ac_packet_011_fields_populated_entirely_from_verify_report(repo):
    repo_root, log_path = repo

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], Path(repo_root)
    )

    invocations = _read_log(log_path)

    # provenance-tracker's check_readiness is the read source.
    assert any(
        rec["module"] == "provenance_tracker" and rec["fn"] == "check_readiness"
        for rec in invocations
    ), f"check_readiness was never called; invocations: {invocations}"

    # No live call into any of the underlying components.
    forbidden = {m for (m, _fns) in FORBIDDEN_MODULES.values()}
    forbidden_calls = [rec for rec in invocations if rec["module"] in forbidden]
    assert forbidden_calls == [], (
        f"build_review_packet called into a component directly: {forbidden_calls}"
    )

    # verification_results — from components[comp-foo].verification_report.
    verification_results = to_plain(field(packet, "verification_results"))
    assert verification_results == {"comp-foo": VERIFICATION_REPORT}

    # compliance_flags — from components[comp-foo].license_scan / secret_scan.
    compliance_flags = field(packet, "compliance_flags")
    license_entries = field(compliance_flags, "license_scan")
    secret_entries = field(compliance_flags, "secret_scan")

    license_entries = list(license_entries)
    secret_entries = list(secret_entries)
    assert len(license_entries) == 1
    assert field(license_entries[0], "component_id") == "comp-foo"
    assert to_plain(field(license_entries[0], "result")) == LICENSE_SCAN

    assert len(secret_entries) == 1
    assert field(secret_entries[0], "component_id") == "comp-foo"
    assert to_plain(field(secret_entries[0], "result")) == SECRET_SCAN

    # provenance_hit_status — from components[comp-foo].hit.
    provenance_hit_status = to_plain(field(packet, "provenance_hit_status"))
    assert provenance_hit_status == {"comp-foo": True}

    # capability_scenarios — from capabilities[P-ZERO-EDIT].capability_scenario_report,
    # keyed by P-id, value exactly as read (itself keyed by P-id, never unwrapped).
    capability_scenarios = to_plain(field(packet, "capability_scenarios"))
    assert capability_scenarios == {"P-ZERO-EDIT": CAPABILITY_SCENARIO_REPORT}

    # Distinct section, never conflated with verification_results.
    assert "P-ZERO-EDIT" not in verification_results