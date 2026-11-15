import json
import subprocess
from pathlib import Path

import pytest

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
        },
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.77,
    "overall": "pass",
}

LICENSE_SCAN_RESULT = {
    "blocked": True,
    "findings": [
        {"file": "foo.py", "license": "SENTINEL-LICENSE-XYZ", "similarity": 0.93}
    ],
}

SECRET_SCAN_RESULT = {
    "flagged": True,
    "findings": [
        {"file": "foo.py", "line": 7, "kind": "SENTINEL-SECRET-KIND"}
    ],
}

CAPABILITY_SCENARIO_REPORT = {
    "P-ZERO-EDIT": {
        "overall": "pass",
        "scenarios": [
            {"id": "SC-ZERO-EDIT-SENTINEL-1", "result": "pass"}
        ],
    }
}

VERIFY_REPORT = {
    "scope": "blast-radius",
    "ready": False,
    "components": {
        "comp-foo": {
            "hit": True,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": LICENSE_SCAN_RESULT,
            "secret_scan": SECRET_SCAN_RESULT,
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
import json

_LOG = {log_path!r}

_REPORT = {report_literal}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    with open(_LOG, "a") as fh:
        fh.write(json.dumps({{
            "fn": "check_readiness",
            "repo_root": str(repo_root),
            "changed_ids": list(changed_ids) if changed_ids is not None else None,
        }}) + "\\n")
    return _REPORT


def last_requirement_failures(component_id, repo_root):
    return []
'''


FORBIDDEN_TEMPLATE = '''\
import json

_LOG = {log_path!r}
_MODULE = {module_name!r}


def _record(fn_name):
    def _call(*args, **kwargs):
        with open(_LOG, "a") as fh:
            fh.write(json.dumps({{"module": _MODULE, "fn": fn_name}}) + "\\n")
        raise RuntimeError(
            "forbidden live call into " + _MODULE + "." + fn_name
        )
    _call.__name__ = fn_name
    return _call


{explicit_defs}


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return _record(name)
'''


FORBIDDEN_MODULES = {
    "verifier-orchestrator": [
        "verify",
        "verify_component",
        "run_verification",
        "orchestrate",
    ],
    "license-scanner": ["scan", "scan_license", "scan_licenses", "license_scan"],
    "secret-scanner": ["scan", "scan_secrets", "secret_scan"],
    "capability-scenario-verifier": [
        "check_capability_provenance",
        "run_capability_gates",
        "verify_capability",
    ],
    "provenance-checker": [
        "current_sealed_key",
        "current_provenance_key",
        "check_provenance",
        "check_sealed_provenance",
    ],
}


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _git(repo_root: Path, *args):
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )


@pytest.fixture
def setup(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    tracker_log = logs / "tracker.log"
    forbidden_log = logs / "forbidden.log"

    # Minimal spec fixture for comp-foo.
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
        "# Foo\n\nA synthetic fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen bar\nThen baz\n```\n",
    )

    # provenance-tracker stand-in.
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        TRACKER_TEMPLATE.format(
            log_path=str(tracker_log),
            report_literal=repr(VERIFY_REPORT),
        ),
    )

    # Forbidden direct dependencies: any call into them is logged.
    for slug, names in FORBIDDEN_MODULES.items():
        module_name = slug.replace("-", "_")
        explicit = "\n".join(
            f"{n} = _record({n!r})" for n in names
        )
        _write(
            repo_root / "gen" / slug / f"{module_name}.py",
            FORBIDDEN_TEMPLATE.format(
                log_path=str(forbidden_log),
                module_name=module_name,
                explicit_defs=explicit,
            ),
        )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    return repo_root, tracker_log, forbidden_log


def _read_log(path: Path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def _normalize_flag_entries(entries):
    out = []
    for entry in entries:
        out.append(
            {
                "component_id": field(entry, "component_id"),
                "result": field(entry, "result"),
            }
        )
    return out


def test_ac_packet_011_fields_sourced_only_from_verify_report(setup):
    repo_root, tracker_log, forbidden_log = setup

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], repo_root
    )

    # provenance-tracker's check_readiness was the read source.
    tracker_calls = [c for c in _read_log(tracker_log) if c["fn"] == "check_readiness"]
    assert tracker_calls, "check_readiness on the provenance-tracker stand-in was never called"

    # verification_results come verbatim from the VerifyReport.
    verification_results = field(packet, "verification_results")
    assert dict(verification_results) == {"comp-foo": VERIFICATION_REPORT}

    # compliance_flags come verbatim from the VerifyReport's scan results.
    compliance_flags = field(packet, "compliance_flags")
    license_entries = _normalize_flag_entries(field(compliance_flags, "license_scan"))
    secret_entries = _normalize_flag_entries(field(compliance_flags, "secret_scan"))
    assert license_entries == [
        {"component_id": "comp-foo", "result": LICENSE_SCAN_RESULT}
    ]
    assert secret_entries == [
        {"component_id": "comp-foo", "result": SECRET_SCAN_RESULT}
    ]

    # provenance_hit_status reflects the VerifyReport's `hit` field.
    provenance_hit_status = field(packet, "provenance_hit_status")
    assert dict(provenance_hit_status) == {"comp-foo": True}

    # capability_scenarios: keyed by P-id, each value the report exactly as read.
    capability_scenarios = field(packet, "capability_scenarios")
    assert dict(capability_scenarios) == {"P-ZERO-EDIT": CAPABILITY_SCENARIO_REPORT}

    # Distinct section from verification_results.
    assert "P-ZERO-EDIT" not in dict(verification_results)

    # No live call into any of the underlying components.
    forbidden_calls = _read_log(forbidden_log)
    assert forbidden_calls == [], (
        "build_review_packet made live calls into components it must only "
        f"read via provenance-tracker: {forbidden_calls}"
    )