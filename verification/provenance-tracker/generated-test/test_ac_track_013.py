import copy
import json
from pathlib import Path

import pytest

import provenance_tracker


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SEALED_HIT = {
    "hit": True,
    "sealed": True,
    "reason": None,
    "verification_report": {"overall": "pass"},
    "license_scan": None,
    "secret_scan": None,
    "owners": ["pipeline-team"],
    "source_hash": "sha256:" + "0" * 64,
    "written_at": "2026-11-02T00:00:00Z",
}

SEALED_MISS_SOURCE_CHANGED = {
    "hit": False,
    "sealed": True,
    "reason": "source_changed",
    "verification_report": None,
    "license_scan": None,
    "secret_scan": None,
    "owners": None,
    "source_hash": None,
    "written_at": None,
}

PLAIN_HIT = {
    "hit": True,
    "verification_report": {
        "component_id": "comp-plain",
        "criteria": [
            {
                "id": "AC-PLAIN-001",
                "covers": "R-PLAIN-001",
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-PLAIN-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "overall": "pass",
    },
    "license_scan": {
        "component_id": "comp-plain",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    },
    "secret_scan": {
        "scope": "full",
        "gate_version": "secret_scanner@0.0.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    },
}

FLAGGED_SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@0.0.0",
    "flagged": True,
    "matches": [
        {
            "rule_id": "AWS Access Key",
            "risk_tier": "high",
            "file": "legacy/seal/config.py",
            "line": 3,
        }
    ],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


PROVENANCE_CHECKER_SRC = '''\
import copy
import json
from types import SimpleNamespace

LOG = {log!r}
SEALED_RESULT = json.loads({sealed!r})
PLAIN_RESULT = json.loads({plain!r})
SEALED_IDS = {{"comp-seal"}}


def _log(name, *args):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"name": name, "args": list(args)}}, default=str) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id, repo_root)
    if component_id in SEALED_IDS:
        return SimpleNamespace(
            owners=["pipeline-team"],
            source_path="legacy/seal/",
            source_hash="sha256:" + "0" * 64,
            verifier_version="verifier-orchestrator@2.0.0",
        )
    return None


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id, repo_root)
    return copy.deepcopy(SEALED_RESULT)


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id, repo_root)
    return SimpleNamespace(
        spec_bundle_hash="sha256:abc123",
        gate_versions={{
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        }},
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id, spec_bundle_hash, gate_versions, repo_root)
    return copy.deepcopy(PLAIN_RESULT)
'''


GATE_RUNNER_SRC = '''\
import json

LOG = {log!r}


def _log(name, *args):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"name": name, "args": list(args)}}, default=str) + "\\n")


_log("component_gate_runner:loaded")


def run_component_gates(*args, **kwargs):
    _log("run_component_gates", *args)
    raise RuntimeError("component-gate-runner must never be called by check_readiness")


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    _log("component_gate_runner:getattr", name)

    def _f(*args, **kwargs):
        _log("component_gate_runner:" + name, *args)
        raise RuntimeError("component-gate-runner must never be called")

    return _f
'''


SECRET_SCANNER_SRC = '''\
import copy
import json

LOG = {log!r}
FLAGGED = json.loads({flagged!r})


def _log(name, *args):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"name": name, "args": list(args)}}, default=str) + "\\n")


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def scan_repository(*args, **kwargs):
    _log("secret_scanner:scan_repository", *args)
    return copy.deepcopy(FLAGGED)


def scan(*args, **kwargs):
    _log("secret_scanner:scan", *args)
    return copy.deepcopy(FLAGGED)


def read_stored_result(*args, **kwargs):
    _log("secret_scanner:read_stored_result", *args)
    return copy.deepcopy(FLAGGED)


def last_result(*args, **kwargs):
    _log("secret_scanner:last_result", *args)
    return copy.deepcopy(FLAGGED)


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)

    def _f(*args, **kwargs):
        _log("secret_scanner:" + name, *args)
        return copy.deepcopy(FLAGGED)

    return _f
'''


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(tmp_path: Path, sealed_result: dict, secret_flagged: bool = False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "invocations.log"
    log.write_text("", encoding="utf-8")

    # Fixture components
    _write(
        repo_root / "specs" / "components" / "seal" / "component.md",
        "---\n"
        "id: comp-seal\n"
        "title: Seal\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/seal/\n"
        "---\n"
        "\n"
        "# comp-seal\n"
        "\n"
        "A sealed fixture component.\n",
    )
    _write(repo_root / "legacy" / "seal" / "seal.py", "VALUE = 1\n")

    _write(
        repo_root / "specs" / "components" / "plain" / "component.md",
        "---\n"
        "id: comp-plain\n"
        "title: Plain\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: false\n"
        "realizes: []\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# comp-plain\n"
        "\n"
        "A generated fixture component.\n",
    )
    _write(repo_root / "gen" / "plain" / "plain.py", "VALUE = 2\n")

    # Fake provenance-checker
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        PROVENANCE_CHECKER_SRC.format(
            log=str(log),
            sealed=json.dumps(sealed_result),
            plain=json.dumps(PLAIN_HIT),
        ),
    )

    # Fake component-gate-runner that records whether it was ever loaded
    _write(
        repo_root / "gen" / "component-gate-runner" / "component_gate_runner.py",
        GATE_RUNNER_SRC.format(log=str(log)),
    )

    if secret_flagged:
        _write(
            repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
            SECRET_SCANNER_SRC.format(
                log=str(log), flagged=json.dumps(FLAGGED_SECRET_SCAN)
            ),
        )
        # A stored whole-repository scan result, in case one is read at all.
        for rel in (
            ".hotdocs/secret-scan.json",
            ".hotdocs/secret-scan/latest.json",
            ".hotdocs/secret_scan.json",
        ):
            _write(repo_root / rel, json.dumps(FLAGGED_SECRET_SCAN))

    return repo_root, log


def read_log(log: Path):
    entries = []
    for line in log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def ids_called(entries, name):
    return [e["args"][0] for e in entries if e["name"] == name]


# ---------------------------------------------------------------------------
# Scenario 1: sealed and non-sealed components routed to their own path
# ---------------------------------------------------------------------------


def test_sealed_and_plain_components_each_checked_by_their_own_path(tmp_path):
    repo_root, log = build_repo(tmp_path, copy.deepcopy(SEALED_HIT))

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is True

    entries = read_log(log)

    assert ids_called(entries, "check_sealed_provenance") == ["comp-seal"]
    assert ids_called(entries, "check_provenance") == ["comp-plain"]
    assert ids_called(entries, "current_provenance_key") == ["comp-plain"]

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT

    gate_runner_events = [
        e for e in entries if e["name"].startswith("component_gate_runner")
        or e["name"] == "run_component_gates"
    ]
    assert gate_runner_events == [], (
        "component-gate-runner was loaded or called: %r" % gate_runner_events
    )


# ---------------------------------------------------------------------------
# Scenario 2: sealed miss reported with the exact reason line
# ---------------------------------------------------------------------------


def test_sealed_miss_reports_exact_reason(tmp_path):
    repo_root, log = build_repo(tmp_path, copy.deepcopy(SEALED_MISS_SOURCE_CHANGED))

    report = provenance_tracker.check_readiness(repo_root)

    assert field(report, "ready") is False

    reasons = list(field(report, "not_ready_reasons"))
    seal_reasons = [r for r in reasons if "comp-seal" in r]
    assert seal_reasons == [
        "comp-seal: sealed provenance source_changed — run hotdocs generate comp-seal"
    ]

    entries = read_log(log)
    gate_runner_events = [
        e for e in entries if e["name"].startswith("component_gate_runner")
        or e["name"] == "run_component_gates"
    ]
    assert gate_runner_events == []


# ---------------------------------------------------------------------------
# Scenario 3: a flagged whole-repository secret scan does not affect a
# sealed component's readiness
# ---------------------------------------------------------------------------


def test_sealed_component_readiness_ignores_flagged_repo_secret_scan(tmp_path):
    repo_root, log = build_repo(
        tmp_path, copy.deepcopy(SEALED_HIT), secret_flagged=True
    )

    report = provenance_tracker.check_readiness(repo_root)

    reasons = list(field(report, "not_ready_reasons"))
    assert [r for r in reasons if "comp-seal" in r] == [], reasons

    components = field(report, "components")
    assert components["comp-seal"] == SEALED_HIT

    entries = read_log(log)
    assert ids_called(entries, "check_sealed_provenance") == ["comp-seal"]