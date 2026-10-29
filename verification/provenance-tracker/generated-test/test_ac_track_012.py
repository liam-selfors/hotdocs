import tempfile
from pathlib import Path

import provenance_tracker


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


IMPACT_ANALYZER_SRC = '''
from pathlib import Path

def compute_blast_radius(changed_ids, repo_root):
    marker = Path(repo_root) / "_impact_analyzer_calls.txt"
    with open(marker, "a") as f:
        f.write(",".join(changed_ids) + "\\n")
    return {
        "impacted": [
            {"component_id": "comp-foo", "reason": "direct", "via": None},
        ],
        "precondition_error": None,
    }
'''

PROVENANCE_CHECKER_SRC = '''
from pathlib import Path

def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    marker = Path(repo_root) / "_provenance_checker_calls.txt"
    with open(marker, "a") as f:
        f.write(component_id + "\\n")
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": component_id,
            "gate_version": "license_scanner@1.0.0",
            "similarity_score": 0.0,
            "block_threshold": 0.7,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@1.0.0",
            "flagged": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }
'''

CAPABILITY_SCENARIO_VERIFIER_SRC = '''
def run_capability_gates(capability_id, repo_root, judge=None, test_author=None):
    return {"hit": True, "capability_scenario_report": {}}

def check_capability_provenance(capability_id, repo_root):
    return {"hit": True, "capability_scenario_report": {}}

def run_capability_scenarios(blast_radius, repo_root, judge=None, test_author=None):
    return {}
'''


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: ratified
owners: [lselfors]
last_ratified_commit: 0000000000000000000000000000000000000
sealed: true
source_path: legacy/foo.py
---

# Foo

A sealed, hand-maintained component used only as a fixture.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — Foo does something, for fixture purposes only.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given foo
When bar
Then baz
```
"""

CONSTRAINTS_MD = """No additional constraints.
"""


def _build_repo_root(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(comp_dir / "component.md", COMPONENT_MD)
    _write(comp_dir / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp_dir / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp_dir / "constraints.md", CONSTRAINTS_MD)

    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        IMPACT_ANALYZER_SRC,
    )
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        PROVENANCE_CHECKER_SRC,
    )
    _write(
        repo_root
        / "gen"
        / "capability-scenario-verifier"
        / "capability_scenario_verifier.py",
        CAPABILITY_SCENARIO_VERIFIER_SRC,
    )


def test_check_readiness_reads_dict_shaped_dependency_results():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _build_repo_root(repo_root)

        report = provenance_tracker.check_readiness(
            repo_root, changed_ids=["comp-foo"]
        )

        scope = report["scope"] if isinstance(report, dict) else report.scope
        ready = report["ready"] if isinstance(report, dict) else report.ready
        components = (
            report["components"]
            if isinstance(report, dict)
            else report.components
        )
        not_ready_reasons = (
            report["not_ready_reasons"]
            if isinstance(report, dict)
            else report.not_ready_reasons
        )

        assert scope == "blast-radius"
        assert not_ready_reasons == []
        assert ready is True

        assert "comp-foo" in components
        foo_result = components["comp-foo"]
        hit = (
            foo_result["hit"]
            if isinstance(foo_result, dict)
            else foo_result.hit
        )
        assert hit is True

        impact_calls = (
            (repo_root / "_impact_analyzer_calls.txt").read_text().strip()
        )
        assert "comp-foo" in impact_calls

        provenance_calls = (
            (repo_root / "_provenance_checker_calls.txt").read_text().strip()
        )
        assert "comp-foo" in provenance_calls