# hotdocs-criterion: sha256:1052e988b224ee8636890afe0f1dc28904c868ebca36c2c37df4a10cc519058d
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
    )
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root, log_path):
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
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
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the first thing.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — Foo MUST do the second thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen the first thing happens\n```\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen the second thing happens\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(comp_dir / "interface" / "library.md", "# Library\n\n```\nfoo() -> None\n```\n")

    verification_report = {
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
                    "message": "result.bar equals 5 failed",
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
    secret_scan = {
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
    license_scan = {
        "blocked": False,
        "matches": [],
        "notified": False,
        "cache_hit": False,
    }
    verify_report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": verification_report,
                "license_scan": license_scan,
                "secret_scan": secret_scan,
            }
        },
        "capabilities": {},
        "secret_scan": secret_scan,
        "not_ready_reasons": ["comp-foo: verification failed (R-FOO-002)"],
    }

    tracker_src = (
        "import copy\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(verify_report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", tracker_src)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")


def _criteria_of(report):
    if isinstance(report, dict) and "criteria" in report:
        return report["criteria"]
    return getattr(report, "criteria")


def test_ac_packet_004_verification_results_show_each_criterion(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"
    _build_fixture(repo_root, log_path)

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001", "R-FOO-002"], repo_root
    )

    assert log_path.is_file(), "provenance-tracker stand-in was never called"

    verification_results = field(packet, "verification_results")
    assert "comp-foo" in verification_results
    report = verification_results["comp-foo"]

    # Not merely an aggregate verdict: each criterion is present individually.
    assert not isinstance(report, str)
    criteria = _criteria_of(report)
    assert isinstance(criteria, (list, tuple))

    by_id = {field(c, "id"): c for c in criteria}
    assert "AC-FOO-001" in by_id
    assert "AC-FOO-002" in by_id
    assert field(by_id["AC-FOO-001"], "result") == "pass"
    assert field(by_id["AC-FOO-002"], "result") == "fail"
    assert field(by_id["AC-FOO-001"], "covers") == "R-FOO-001"
    assert field(by_id["AC-FOO-002"], "covers") == "R-FOO-002"

    # The per-requirement breakdown is carried too, not collapsed.
    if has_field(report, "requirement_results"):
        rr = field(report, "requirement_results")
        assert rr["R-FOO-001"] == "pass"
        assert rr["R-FOO-002"] == "fail"