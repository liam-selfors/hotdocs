from pathlib import Path

import pytest

import review_packet_builder


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


COMPONENT_MD = """---
id: comp-foo
title: Foo Component
status: draft
owners: [owner@example.com]
sealed: true
source_path: legacy/foo.py
---

# Foo Component
"""

REQUIREMENT_FOO_001 = """# R-FOO-001

**R-FOO-001** -- Foo must do the existing thing.
"""

REQUIREMENT_FOO_002 = """# R-FOO-002

**R-FOO-002** -- Foo must do the new thing.
"""

ACCEPTANCE_FOO_001 = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given foo
When bar
Then baz
```
"""

ACCEPTANCE_FOO_002 = """# AC-FOO-002

Covers: R-FOO-002
Kind: generated-test

```gherkin
Given foo changed
When bar runs
Then baz holds
```
"""

FAKE_PROVENANCE_TRACKER = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "blast-radius" if changed_ids else "whole-corpus",
        "ready": True,
        "components": {},
        "capabilities": {},
        "not_ready_reasons": [],
    }


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "fake-attempt",
        "component_id": component_id,
        "timestamp": "2026-10-31T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


def _write_fixture(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True)
    (comp_dir / "acceptance").mkdir(parents=True)

    (comp_dir / "component.md").write_text(COMPONENT_MD)
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_FOO_001)
    (comp_dir / "requirements" / "R-FOO-002.md").write_text(REQUIREMENT_FOO_002)
    (comp_dir / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_FOO_001)
    (comp_dir / "acceptance" / "AC-FOO-002.md").write_text(ACCEPTANCE_FOO_002)

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER)


def test_changed_requirements_includes_new_requirement(tmp_path):
    repo_root = tmp_path
    _write_fixture(repo_root)

    packet = review_packet_builder.build_review_packet(
        changed_ids=["R-FOO-002"],
        repo_root=repo_root,
    )

    changed_requirements = _get(packet, "changed_requirements")
    assert changed_requirements is not None
    assert "R-FOO-002" in list(changed_requirements)