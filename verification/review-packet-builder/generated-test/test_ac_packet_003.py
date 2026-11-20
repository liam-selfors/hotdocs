# hotdocs-criterion: sha256:4cbe8adc31f60078c712355415e4d0ea3521b3831015d5dd62027fb5a209447d
import importlib.util
import subprocess
import sys
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def _verification_report(component_id, req_id, ac_id):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": ac_id, "covers": req_id, "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {req_id: "pass"},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [{
            "kind": "python", "path": ".", "definition_sha256": None,
            "adapter_sha256": "sha256:" + "0" * 64, "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }],
        "overall": "pass",
    }


def _check_result(component_id, req_id, ac_id):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, req_id, ac_id),
        "license_scan": {"blocked": False, "findings": []},
        "secret_scan": {"flagged": False, "findings": []},
    }


def _component_fixture(repo_root, slug, upper):
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
        "**R-" + upper + "-001** — The component MUST do its thing.\n",
    )
    _write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\nCovers: R-" + upper + "-001\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )


def test_regenerated_components_lists_exactly_the_verify_report_components(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    _component_fixture(repo_root, "foo", "FOO")
    _component_fixture(repo_root, "bar", "BAR")

    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": _check_result("comp-foo", "R-FOO-001", "AC-FOO-001"),
            "comp-bar": _check_result("comp-bar", "R-BAR-001", "AC-BAR-001"),
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }

    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return REPORT\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", source)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture")

    packet = review_packet_builder.build_review_packet(["comp-foo", "comp-bar"], repo_root)

    assert log_path.is_file(), "provenance-tracker stand-in was never called"
    assert "check_readiness" in log_path.read_text(encoding="utf-8")

    regenerated = list(field(packet, "regenerated_components"))
    assert len(regenerated) == 2, regenerated
    assert sorted(regenerated) == ["comp-bar", "comp-foo"]