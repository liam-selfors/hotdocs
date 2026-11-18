# hotdocs-criterion: sha256:155f62e871d75030e1820ac89319ef7af2d4a2e6e89027761c0728c2ff37793c
import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    })
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(repo_root), check=True, capture_output=True, env=env,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _component(repo_root, slug, upper):
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        "id: comp-" + slug + "\n"
        "title: " + slug.capitalize() + "\n"
        "status: draft\n"
        "owners: [tester]\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n\n"
        "# " + slug.capitalize() + "\n\nA fixture component.\n",
    )
    _write(
        base / "requirements" / ("R-" + upper + "-001.md"),
        "# R-" + upper + "-001\n\n**R-" + upper + "-001** — The component MUST work.\n",
    )
    _write(
        base / "acceptance" / ("AC-" + upper + "-001.md"),
        "# AC-" + upper + "-001\n\nCovers: R-" + upper + "-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    _write(base / "interface" / "library.md", "# Library\n\n```\nrun() -> None\n```\n")
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _verification_report(component_id, upper):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-" + upper + "-001", "covers": "R-" + upper + "-001",
             "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-" + upper + "-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "mutation_error": None,
        "overall": "pass",
    }


def _provenance_check_result(component_id, upper):
    return {
        "hit": True,
        "verification_report": _verification_report(component_id, upper),
        "license_scan": {"blocked": False, "findings": []},
        "secret_scan": {"flagged": False, "findings": []},
    }


def test_regenerated_components_lists_exactly_report_component_keys(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "check_readiness_calls.log"

    _component(repo_root, "alpha", "ALPHA")
    _component(repo_root, "beta", "BETA")
    _component(repo_root, "gamma", "GAMMA")

    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-alpha": _provenance_check_result("comp-alpha", "ALPHA"),
            "comp-beta": _provenance_check_result("comp-beta", "BETA"),
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }

    stand_in = (
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write('check_readiness\\n')\n"
        "    return " + repr(report) + "\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", stand_in)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial fixture")

    packet = review_packet_builder.build_review_packet(["comp-alpha"], repo_root)

    assert log_path.is_file(), "provenance-tracker stand-in check_readiness was never called"
    assert "check_readiness" in log_path.read_text()

    regenerated = list(field(packet, "regenerated_components"))
    assert len(regenerated) == 2
    assert sorted(regenerated) == ["comp-alpha", "comp-beta"]
    assert "comp-gamma" not in regenerated