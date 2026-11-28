# hotdocs-criterion: sha256:1d02895fbb9a3e4170d4c94d363cf5e303badb7ff628776c692628499bbfc22b
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
        ["git"] + list(args),
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write_component(repo_root, slug, upper):
    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " Component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# " + slug.capitalize() + "\n"
        "\n"
        "A fixture component.\n",
    )
    rid = "R-" + upper + "-001"
    acid = "AC-" + upper + "-001"
    _write(
        comp_dir / "requirements" / (rid + ".md"),
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** - The component MUST do its one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / (acid + ".md"),
        "# " + acid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the component\n"
        "When it runs\n"
        "Then it does its one thing\n"
        "```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")


def _verification_report(component_id, upper):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-" + upper + "-001",
                "covers": "R-" + upper + "-001",
                "kind": "generated-test",
                "result": "pass",
            }
        ],
        "requirement_results": {"R-" + upper + "-001": "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass",
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
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def test_ac_packet_006_provenance_hit_status_per_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _write_component(repo_root, "alpha", "ALPHA")
    _write_component(repo_root, "beta", "BETA")

    verify_report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-alpha": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report("comp-alpha", "ALPHA"),
                "license_scan": _license_scan_result(),
                "secret_scan": _secret_scan_result(),
            },
            "comp-beta": {
                "hit": False,
                "reason": "no manifest",
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
        },
        "capabilities": {},
        "secret_scan": _secret_scan_result(),
        "not_ready_reasons": [
            "comp-beta: no provenance for current spec state - run hotdocs generate comp-beta"
        ],
    }

    tracker_src = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return " + repr(verify_report) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        tracker_src,
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")

    changed_ids = ["comp-alpha", "comp-beta", "R-ALPHA-001", "R-BETA-001"]
    packet = review_packet_builder.build_review_packet(changed_ids, repo_root)

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert log_path.read_text(encoding="utf-8").strip() != ""

    status = field(packet, "provenance_hit_status")
    assert isinstance(status, dict)

    # Both components are shown explicitly, never left to inference.
    assert "comp-alpha" in status
    assert "comp-beta" in status

    # Each reflects its own provenance-hit state accurately.
    assert status["comp-alpha"] is True
    assert status["comp-beta"] is False