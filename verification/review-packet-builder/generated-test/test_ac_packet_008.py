# hotdocs-criterion: sha256:eb08e7c63d4493ac8e515f445316b23608c070b3b1b392ecb58d51d1147b3194
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
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
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen it does the thing\n```\n",
    )
    _write(comp_dir / "constraints.md", "No constraints.\n")
    _write(repo_root / "legacy" / "foo" / "foo.py", "X = 1\n")


def _verify_report():
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
             "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
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
    license_scan = {"blocked": False, "matches": []}
    return {
        "scope": "blast-radius",
        "ready": True,
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
        "not_ready_reasons": [],
    }


def _write_tracker_stand_in(repo_root, log_path):
    source = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return " + repr(_verify_report()) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", source)


def test_ac_packet_008_residual_risk_includes_mutation_score_below_one(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _build_fixture(repo_root)
    _write_tracker_stand_in(repo_root, log_path)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    packet = review_packet_builder.build_review_packet(
        ["comp-foo", "R-FOO-001"], repo_root
    )

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8")

    residual_risk = field(packet, "residual_risk")
    assert isinstance(residual_risk, list)

    matching = []
    for entry in residual_risk:
        assert not isinstance(entry, str), "residual_risk entry must be an object, not a bare string"
        if field(entry, "component_id") == "comp-foo":
            matching.append(entry)

    assert matching, "residual_risk has no entry for comp-foo: " + repr(residual_risk)

    messages = [field(entry, "message") for entry in matching]
    assert any(
        isinstance(m, str) and m.strip() and "mutation" in m.lower() for m in messages
    ), "no comp-foo residual_risk message describes the mutation_score finding: " + repr(messages)