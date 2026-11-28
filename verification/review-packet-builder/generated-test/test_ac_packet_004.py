# hotdocs-criterion: sha256:7a0a357df21bf8b351b36db96158cd19ab4926019b746d61289d4380fdea0f29
"""AC-PACKET-004: verification_results shows each criterion result
individually, not only an aggregate pass/fail (R-PACKET-004)."""

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
        [
            "git",
            "-c", "user.name=hotdocs-test",
            "-c", "user.email=hotdocs-test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "pass",
            },
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {
                    "message": "result.foo equals 5 failed",
                    "expected": 5,
                    "actual": 3,
                },
                "failure_origin": "implementation",
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "fail",
    }


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


def _license_scan_result():
    return {
        "blocked": False,
        "matches": [],
        "gate_version": "license_scanner@1.0.0",
        "cache_hit": False,
    }


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(),
                "license_scan": _license_scan_result(),
                "secret_scan": _secret_scan_result(),
            }
        },
        "capabilities": {},
        "secret_scan": _secret_scan_result(),
        "not_ready_reasons": ["comp-foo: verification overall=fail"],
    }


def _build_fixture(repo_root, log_path):
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
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
        "A fixture component.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the first thing.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — Foo MUST do the second thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen the first thing happens\n```\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen the second thing happens\n```\n",
    )
    _write(repo_root / "legacy" / "foo" / "foo.py", "VALUE = 1\n")

    fake_src = (
        "from pathlib import Path\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness ' + repr(changed_ids) + '\\n')\n"
        "    return _REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('last_requirement_failures ' + repr(component_id) + '\\n')\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        fake_src,
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")


def test_verification_results_show_each_criterion_individually(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _build_fixture(repo_root, log_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001", "R-FOO-002"], repo_root
    )

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8")

    results = field(packet, "verification_results")
    assert "comp-foo" in results, results
    report = results["comp-foo"]

    criteria = field(report, "criteria")
    by_id = {}
    for c in criteria:
        by_id[field(c, "id")] = c

    assert "AC-FOO-001" in by_id, criteria
    assert "AC-FOO-002" in by_id, criteria
    assert field(by_id["AC-FOO-001"], "result") == "pass"
    assert field(by_id["AC-FOO-002"], "result") == "fail"
    assert field(by_id["AC-FOO-001"], "covers") == "R-FOO-001"
    assert field(by_id["AC-FOO-002"], "covers") == "R-FOO-002"

    requirement_results = field(report, "requirement_results")
    assert requirement_results["R-FOO-001"] == "pass"
    assert requirement_results["R-FOO-002"] == "fail"