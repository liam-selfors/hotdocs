import dataclasses
import os
import subprocess
import tempfile
from pathlib import Path

import review_packet_builder


OLD_SENTINEL = "SENTINEL_LINE_OLD_a1b2c3d4"
NEW_SENTINEL = "SENTINEL_LINE_NEW_e5f6g7h8"
OLD_VALUE = "old-value-a1b2c3d4"
NEW_VALUE = "new-value-e5f6g7h8"
EXTRA_NEW = "extra-new-function-e5f6g7h8"

DIFF_FINGERPRINTS = [OLD_SENTINEL, NEW_SENTINEL, OLD_VALUE, NEW_VALUE, EXTRA_NEW]


def _git(repo_root, *args):
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_fixture_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "lselfors@gmail.com")
    _git(repo_root, "config", "user.name", "Test Author")

    component_md = """---
id: comp-foo
title: Foo Fixture Component
status: draft
owners: [lselfors@gmail.com]
sealed: false
depends_on: []
---

# comp-foo

Fixture component used to exercise review-packet-builder's handling of a
substantial generated-code change.
"""
    requirement_md = """# R-FOO-001

**R-FOO-001** -- `foo()` MUST return a non-empty string.
"""
    acceptance_md = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given foo()
When it is called
Then it returns a non-empty string
```
"""
    interface_md = """# Library

```
foo() -> str
```
"""

    _write(repo_root / "specs/components/foo/component.md", component_md)
    _write(repo_root / "specs/components/foo/requirements/R-FOO-001.md", requirement_md)
    _write(repo_root / "specs/components/foo/acceptance/AC-FOO-001.md", acceptance_md)
    _write(repo_root / "specs/components/foo/interface/library.md", interface_md)

    old_gen = f"""# fixture generated code for comp-foo
# {OLD_SENTINEL}
def foo():
    return "{OLD_VALUE}"
"""
    _write(repo_root / "gen/foo/foo.py", old_gen)

    _git(repo_root, "add", "-A")
    _git(repo_root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial generation of comp-foo")

    new_gen = f"""# fixture generated code for comp-foo, substantially regenerated
# {NEW_SENTINEL}
def foo():
    return "{NEW_VALUE}"


def foo_helper():
    return "{EXTRA_NEW}"
"""
    _write(repo_root / "gen/foo/foo.py", new_gen)

    _git(repo_root, "add", "-A")
    _git(repo_root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "substantial regeneration of comp-foo")


def _write_fake_provenance_tracker(repo_root: Path) -> None:
    module_src = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": {
                    "component_id": "comp-foo",
                    "criteria": [
                        {
                            "id": "AC-FOO-001",
                            "covers": "R-FOO-001",
                            "kind": "compiled",
                            "result": "pass",
                        }
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                },
                "license_scan": {
                    "component_id": "comp-foo",
                    "blocked": False,
                    "findings": [],
                },
                "secret_scan": {
                    "component_id": "comp-foo",
                    "flagged": False,
                    "findings": [],
                },
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "2026-01-01T00:00:00Z-000000",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''
    _write(repo_root / "gen/provenance-tracker/provenance_tracker.py", module_src)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _iter_children(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for field in dataclasses.fields(obj):
            yield getattr(obj, field.name)
    elif isinstance(obj, dict):
        for value in obj.values():
            yield value
    elif isinstance(obj, (list, tuple, set)):
        for value in obj:
            yield value
    elif hasattr(obj, "__dict__"):
        for value in vars(obj).values():
            yield value


def _collect_strings(obj, acc):
    if isinstance(obj, str):
        acc.append(obj)
        return
    if obj is None or isinstance(obj, (int, float, bool)):
        return
    for child in _iter_children(obj):
        _collect_strings(child, acc)


def test_packet_excludes_generated_code_diff_for_substantially_changed_component():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _build_fixture_repo(repo_root)
        _write_fake_provenance_tracker(repo_root)

        packet = review_packet_builder.build_review_packet(["comp-foo"], repo_root)

        regenerated = _get(packet, "regenerated_components", [])
        assert "comp-foo" in regenerated

        verification_results = _get(packet, "verification_results", {})
        comp_foo_report = _get(verification_results, "comp-foo", {})
        assert _get(comp_foo_report, "overall") == "pass"

        strings = []
        _collect_strings(packet, strings)
        blob = "\n".join(strings)

        for fingerprint in DIFF_FINGERPRINTS:
            assert fingerprint not in blob, (
                f"generated-code diff content {fingerprint!r} leaked into the review packet"
            )