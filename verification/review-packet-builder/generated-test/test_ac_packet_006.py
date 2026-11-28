# hotdocs-criterion: sha256:2ff437ba7e2bad2bf6c82c4d77239175278c1afc86595e680b0a8e4c6a8267a8
"""AC-PACKET-006: provenance_hit_status reflects per-component hit/miss accurately.

Covers: R-PACKET-006
"""

import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, r_id, ac_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": ac_id, "covers": r_id, "kind": "llm-judge", "result": "pass", "rationale": None},
        ],
        "requirement_results": {r_id: "pass"},
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
    return {"blocked": False, "matches": []}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root, slug, suffix):
    comp_id = "comp-" + slug
    r_id = "R-" + suffix + "-001"
    ac_id = "AC-" + suffix + "-001"
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        "id: " + comp_id + "\n"
        "title: Fixture component " + slug + "\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n\n"
        "# Fixture component " + slug + "\n\n"
        "## Purpose\n\nA fixture component.\n",
    )
    _write(
        base / "requirements" / (r_id + ".md"),
        "# " + r_id + "\n\n**" + r_id + "** — The component MUST do its fixture thing.\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\nCovers: " + r_id + "\nKind: llm-judge\n\n"
        "```gherkin\nGiven a fixture\nWhen it runs\nThen it does its fixture thing\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")
    _write(base / "interface" / "library.md", "# Library\n\n```\nfoo() -> None\n```\n")
    return comp_id, r_id, ac_id


def _git(repo_root, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=hotdocs-test",
            "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_provenance_hit_status_per_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    hit_id, hit_r, hit_ac = _write_component(repo_root, "alpha", "ALPHA")
    miss_id, miss_r, miss_ac = _write_component(repo_root, "beta", "BETA")

    verify_report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            hit_id: {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(hit_id, hit_r, hit_ac),
                "license_scan": _license_scan_result(),
                "secret_scan": _secret_scan_result(),
            },
            miss_id: {
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
            miss_id + ": no provenance for current spec state — run hotdocs generate " + miss_id
        ],
    }

    tracker_src = (
        "from pathlib import Path\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(verify_report) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return _REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", tracker_src)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")

    changed_ids = [hit_id, hit_r, miss_id, miss_r]
    packet = review_packet_builder.build_review_packet(changed_ids, repo_root)

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8")

    status = field(packet, "provenance_hit_status")
    assert isinstance(status, dict), "provenance_hit_status must be a per-component mapping"

    # Both components shown explicitly — the miss is not left to be inferred by absence.
    assert hit_id in status, "hit component missing from provenance_hit_status"
    assert miss_id in status, "miss component missing from provenance_hit_status"

    assert status[hit_id] is True, "hit component must be reported as a hit: " + repr(status[hit_id])
    assert status[miss_id] is False, "miss component must be reported as a miss: " + repr(status[miss_id])