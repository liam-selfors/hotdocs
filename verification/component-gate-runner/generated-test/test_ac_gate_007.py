import os
import textwrap

import pytest

import component_gate_runner


def _get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))


def _setup_sealed_repo(tmp_path):
    repo_root = tmp_path

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        """\
        ---
        id: comp-foo
        title: Foo
        status: draft
        owners: [lselfors@gmail.com]
        sealed: true
        source_path: legacy/foo.py
        ---

        # Foo

        ## Purpose

        Fixture sealed component for AC-GATE-007.
        """,
    )

    log_path = str(repo_root / "_test_invocations.log").replace("\\", "\\\\")

    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        f"""\
        import os

        GATE_VERSION = "verifier-orchestrator@2.0.0"

        _LOG_PATH = r"{log_path}"


        def verify(component_id, repo_root, judge=None, test_author=None):
            with open(_LOG_PATH, "a") as f:
                f.write("verify\\n")
            overall = os.environ.get("FAKE_VERIFY_OVERALL", "pass")
            result = "pass" if overall == "pass" else "fail"
            return {{
                "component_id": component_id,
                "criteria": [
                    {{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": result}},
                ],
                "requirement_results": {{"R-FOO-001": result}},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": overall,
            }}
        """,
    )

    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        f"""\
        _LOG_PATH = r"{log_path}"


        def scan(component_id, repo_root):
            with open(_LOG_PATH, "a") as f:
                f.write("license_scan\\n")
            return {{
                "component_id": component_id,
                "gate_version": "license_scanner@3.1.0",
                "similarity_score": 0.0,
                "block_threshold": 0.70,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }}


        def gate_version(repo_root):
            return "license_scanner@3.1.0"
        """,
    )

    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        f"""\
        _LOG_PATH = r"{log_path}"


        def scan(repo_root):
            with open(_LOG_PATH, "a") as f:
                f.write("secret_scan\\n")
            return {{
                "scope": "full",
                "gate_version": "secret_scanner@2.0.0",
                "flagged": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }}


        def gate_version(repo_root):
            return "secret_scanner@2.0.0"
        """,
    )

    return repo_root


def _read_log(repo_root):
    log_file = repo_root / "_test_invocations.log"
    if not log_file.exists():
        return []
    return [line for line in log_file.read_text().splitlines() if line]


def test_sealed_component_skips_generation_and_runs_verify_and_scans(tmp_path):
    repo_root = _setup_sealed_repo(tmp_path)
    os.environ["FAKE_VERIFY_OVERALL"] = "pass"
    try:
        result = component_gate_runner.run_component_gates(
            "comp-foo", repo_root, model="test-model",
        )
    finally:
        os.environ.pop("FAKE_VERIFY_OVERALL", None)

    log_lines = _read_log(repo_root)
    assert log_lines.count("verify") == 1
    assert log_lines.count("license_scan") == 1
    assert log_lines.count("secret_scan") == 1
    assert len(log_lines) == 3

    assert _get(result, "provenance_hit") is False


def test_sealed_component_verify_fail_blocks_with_verification_failed(tmp_path):
    repo_root = _setup_sealed_repo(tmp_path)
    os.environ["FAKE_VERIFY_OVERALL"] = "fail"
    try:
        result = component_gate_runner.run_component_gates(
            "comp-foo", repo_root, model="test-model",
        )
    finally:
        os.environ.pop("FAKE_VERIFY_OVERALL", None)

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "verification_failed"