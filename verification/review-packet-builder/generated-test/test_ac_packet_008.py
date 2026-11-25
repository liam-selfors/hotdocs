# hotdocs-criterion: sha256:e01166c56c9926eca179270cfbb179575bf674f9dfd5bedf869ec20ec1c8d00d
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _secret_scan_result():
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


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "pass",
    }


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(),
                "license_scan": {"blocked": False},
                "secret_scan": _secret_scan_result(),
            }
        },
        "capabilities": {},
        "secret_scan": _secret_scan_result(),
        "not_ready_reasons": [],
    }


def _build_repo(repo_root, log_path):
    repo_root.mkdir(parents=True, exist_ok=True)
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do the thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "VALUE = 1\n")

    fake_source = (
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        fake_source,
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")


def test_ac_packet_008_residual_risk_includes_low_mutation_score(tmp_path):
    repo_root = tmp_path / "repo"
    log_path = tmp_path / "tracker_calls.log"
    _build_repo(repo_root, log_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], repo_root
    )

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8")

    residual_risk = field(packet, "residual_risk")
    assert isinstance(residual_risk, list)

    matches = [
        entry for entry in residual_risk
        if field(entry, "component_id") == "comp-foo"
    ]
    assert matches, "residual_risk has no entry for comp-foo: " + repr(residual_risk)

    found = False
    for entry in matches:
        message = field(entry, "message")
        assert isinstance(message, str) and message.strip()
        lowered = message.lower()
        if "mutation" in lowered or "0.92" in lowered:
            found = True
    assert found, "no residual_risk entry for comp-foo describes the mutation score finding: " + repr(matches)

    # residual risk is its own section, distinct from pass/fail results
    verification_results = field(packet, "verification_results")
    assert verification_results is not residual_risk