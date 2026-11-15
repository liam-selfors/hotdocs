import review_packet_builder

import os
import subprocess
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HIT_ID = "comp-alpha"
MISS_ID = "comp-beta"


def _verification_report(component_id, req_id, ac_id):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": ac_id,
                "covers": req_id,
                "kind": "compiled",
                "result": "pass",
            }
        ],
        "requirement_results": {req_id: "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "overall": "pass",
    }


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            HIT_ID: {
                "hit": True,
                "verification_report": _verification_report(
                    HIT_ID, "R-ALPHA-001", "AC-ALPHA-001"
                ),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
            MISS_ID: {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
        },
        "capabilities": {},
        "not_ready_reasons": [
            MISS_ID
            + ": no provenance for current spec state - run hotdocs generate "
            + MISS_ID
        ],
    }


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root, slug, upper):
    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} fixture component\n"
        "status: draft\n"
        "owners: [fixture-owner]\n"
        "depends_on: []\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n\n"
        f"# comp-{slug}\n\nA synthetic fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** - The component MUST do its thing.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\ndo_thing() -> None\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "legacy" / slug / f"{slug}.py", "def do_thing():\n    return None\n")


def _write_tracker_stand_in(repo_root, log_path):
    report_literal = repr(_verify_report())
    source = (
        "from pathlib import Path\n\n"
        f"_LOG = {str(log_path)!r}\n"
        f"_REPORT = {report_literal}\n\n\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness ' + repr(changed_ids) + '\\n')\n"
        "    import copy\n"
        "    report = copy.deepcopy(_REPORT)\n"
        "    report['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
        "    return report\n\n\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", source
    )


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
    )
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        env=env,
    )


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"
    _write_component(repo_root, "alpha", "ALPHA")
    _write_component(repo_root, "beta", "BETA")
    _write_tracker_stand_in(repo_root, log_path)
    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")
    return repo_root, log_path


def test_provenance_hit_status_reflects_hit_and_miss_per_component(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)

    changed_ids = [HIT_ID, MISS_ID, "R-ALPHA-001", "R-BETA-001"]
    packet = review_packet_builder.build_review_packet(changed_ids, Path(repo_root))

    # The provenance-tracker stand-in was actually consulted.
    assert log_path.exists(), "provenance-tracker stand-in was never invoked"
    assert "check_readiness" in log_path.read_text(encoding="utf-8")

    status = field(packet, "provenance_hit_status")
    assert isinstance(status, dict)

    # Both components are shown explicitly, never left to be inferred.
    assert HIT_ID in status, f"{HIT_ID} missing from provenance_hit_status: {status!r}"
    assert MISS_ID in status, f"{MISS_ID} missing from provenance_hit_status: {status!r}"

    # Each component's status is accurate.
    assert status[HIT_ID] is True, f"expected {HIT_ID} hit True, got {status[HIT_ID]!r}"
    assert status[MISS_ID] is False, f"expected {MISS_ID} hit False, got {status[MISS_ID]!r}"