import os
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HIT_COMPONENT = "comp-alpha"
MISS_COMPONENT = "comp-beta"


def _verification_report(component_id):
    req = "R-ALPHA-001" if component_id == HIT_COMPONENT else "R-BETA-001"
    ac = "AC-ALPHA-001" if component_id == HIT_COMPONENT else "AC-BETA-001"
    return {
        "component_id": component_id,
        "criteria": [
            {"id": ac, "covers": req, "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {req: "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }


def _verify_report():
    return {
        "scope": "blast-radius",
        "ready": False,
        "components": {
            HIT_COMPONENT: {
                "hit": True,
                "verification_report": _verification_report(HIT_COMPONENT),
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            },
            MISS_COMPONENT: {
                "hit": False,
                "verification_report": None,
                "license_scan": None,
                "secret_scan": None,
            },
        },
        "capabilities": {},
        "not_ready_reasons": [
            MISS_COMPONENT
            + ": no provenance for current spec state — run hotdocs generate "
            + MISS_COMPONENT
        ],
    }


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root: Path, slug: str, prefix: str):
    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n\n"
        f"# comp-{slug}\n\nA synthetic fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / f"R-{prefix}-001.md",
        f"# R-{prefix}-001\n\n**R-{prefix}-001** — The component MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{prefix}-001.md",
        f"# AC-{prefix}-001\n\nCovers: R-{prefix}-001\nKind: compiled\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it does one thing\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(_dummy := (repo_root / "legacy" / slug / f"{slug}.py"), "VALUE = 1\n")


def _git(repo_root: Path, *args):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
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


def _build_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_component(repo_root, "alpha", "ALPHA")
    _write_component(repo_root, "beta", "BETA")

    report_literal = repr(_verify_report())
    stand_in = (
        "import copy\n"
        "\n"
        f"_REPORT = {report_literal}\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        stand_in,
    )

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "initial fixture")

    # A spec change in this PR touching both components.
    for slug, prefix in (("alpha", "ALPHA"), ("beta", "BETA")):
        req = repo_root / "specs" / "components" / slug / "requirements" / f"R-{prefix}-001.md"
        req.write_text(
            f"# R-{prefix}-001\n\n**R-{prefix}-001** — The component MUST do one thing, clearly.\n",
            encoding="utf-8",
        )

    return repo_root


def test_provenance_hit_status_reflects_hit_and_miss_per_component(tmp_path):
    repo_root = _build_repo(tmp_path)

    changed_ids = [HIT_COMPONENT, MISS_COMPONENT, "R-ALPHA-001", "R-BETA-001"]
    packet = review_packet_builder.build_review_packet(changed_ids, repo_root)

    status = field(packet, "provenance_hit_status")

    # Shown per component, visibly: both components present as explicit keys.
    assert HIT_COMPONENT in status, (
        f"{HIT_COMPONENT} missing from provenance_hit_status: {status!r}"
    )
    assert MISS_COMPONENT in status, (
        f"{MISS_COMPONENT} missing from provenance_hit_status: {status!r}"
    )

    # Accurate per component: hit is true, miss is false (explicitly, not absent/None).
    assert status[HIT_COMPONENT] is True, (
        f"expected {HIT_COMPONENT} to be a provenance hit, got {status[HIT_COMPONENT]!r}"
    )
    assert status[MISS_COMPONENT] is False, (
        f"expected {MISS_COMPONENT} to be a provenance miss, got {status[MISS_COMPONENT]!r}"
    )