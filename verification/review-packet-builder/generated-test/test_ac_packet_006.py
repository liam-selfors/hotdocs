# hotdocs-criterion: sha256:a1c58b44854d9adb2a7689187f21851eacdd900fa67c0172051c208227928878
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
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _component(repo_root, slug, upper):
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + " component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n\n"
        "# " + slug + "\n\nA fixture component.\n",
    )
    _write(
        base / "requirements" / ("R-" + upper + "-001.md"),
        "**R-" + upper + "-001** — The " + slug + " component MUST do its job.\n",
    )
    _write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\n"
        "Covers: R-" + upper + "-001\n"
        "Kind: llm-judge\n\n"
        "```gherkin\n"
        "Given the " + slug + " component\n"
        "When it runs\n"
        "Then it does its job\n"
        "```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _verification_report(component_id, req_id, ac_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": ac_id, "covers": req_id, "kind": "llm-judge", "result": "pass", "rationale": "ok"}
        ],
        "requirement_results": {req_id: "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": "pass",
    }


def _secret_scan():
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


def _license_scan():
    return {"blocked": False, "matches": []}


def test_ac_packet_006_provenance_hit_status_per_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _component(repo_root, "alpha", "ALPHA")
    _component(repo_root, "beta", "BETA")

    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial")

    report = {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            "comp-alpha": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report("comp-alpha", "R-ALPHA-001", "AC-ALPHA-001"),
                "license_scan": _license_scan(),
                "secret_scan": _secret_scan(),
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
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-beta: no provenance for current spec state — run hotdocs generate comp-beta"
        ],
    }

    tracker_src = (
        "REPORT = " + repr(report) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return REPORT\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", tracker_src)

    changed_ids = ["comp-alpha", "comp-beta", "R-ALPHA-001", "R-BETA-001"]
    packet = review_packet_builder.build_review_packet(changed_ids, repo_root)

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8")

    status = field(packet, "provenance_hit_status")
    assert "comp-alpha" in status, "hit component's status must be shown explicitly"
    assert "comp-beta" in status, "miss component's status must be shown explicitly, not inferred"
    assert status["comp-alpha"] is True
    assert status["comp-beta"] is False