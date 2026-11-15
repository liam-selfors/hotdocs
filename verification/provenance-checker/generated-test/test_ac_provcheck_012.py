import copy
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


COMPONENT_ID = "comp-foo"
OWNERS = ["pipeline-team", "alice"]
SOURCE_PATH = "pipeline/foo/"
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
WRITTEN_AT = "2026-11-02T00:00:00Z"
DUMMY_HASH = "sha256:" + "0" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SEALED_COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [pipeline-team, alice]
sealed: true
source_path: pipeline/foo/
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""

UNSEALED_COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [pipeline-team, alice]
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""

FAKE_VERIFIER = '''GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    raise AssertionError("verify must not be called by check_sealed_provenance")
'''

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(tmp_path, sealed=True):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", SEALED_COMPONENT_MD if sealed else UNSEALED_COMPONENT_MD)
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "pipeline" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")
    write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        FAKE_VERIFIER,
    )
    return repo_root


def valid_manifest(source_hash):
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": COMPONENT_ID,
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": source_hash,
        "verifier_version": VERIFIER_VERSION,
        "characterization": {"overall": "pass", "criteria_passed": 2, "criteria_total": 2},
        "written_at": WRITTEN_AT,
    }


def manifest_path(repo_root):
    return repo_root / "pipeline" / "foo" / ".sealed-provenance.json"


def snapshot(root):
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if "__pycache__" in rel.parts:
            continue
        if p.is_dir():
            out[rel.as_posix() + "/"] = None
        else:
            out[rel.as_posix()] = p.read_bytes()
    return out


def current_hash(repo_root):
    key = provenance_checker.current_sealed_key(COMPONENT_ID, repo_root)
    assert key is not None
    h = field(key, "source_hash")
    assert isinstance(h, str) and h.startswith("sha256:")
    return h


def run_check(repo_root):
    before = snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo_root)
    after = snapshot(repo_root)
    assert after == before, "check_sealed_provenance modified files under repo_root"
    return result


def assert_miss(result, reason, sealed=True):
    assert field(result, "reason") == reason
    assert field(result, "hit") is False
    assert field(result, "sealed") is sealed
    for name in ("verification_report", "owners", "source_hash", "written_at",
                 "license_scan", "secret_scan"):
        assert field(result, name) is None, name


# ---------------------------------------------------------------- valid hit

def test_valid_current_manifest_is_hit(tmp_path):
    repo_root = build_repo(tmp_path)
    source_hash = current_hash(repo_root)
    manifest_path(repo_root).write_text(json.dumps(valid_manifest(source_hash)), encoding="utf-8")

    result = run_check(repo_root)

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "sealed") is True
    assert field(result, "verification_report") == {"overall": "pass"}
    assert field(result, "owners") == OWNERS
    assert field(result, "written_at") == WRITTEN_AT
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


# ---------------------------------------------------------------- missing

def test_manifest_missing(tmp_path):
    repo_root = build_repo(tmp_path)
    assert not manifest_path(repo_root).exists()
    result = run_check(repo_root)
    assert_miss(result, "manifest_missing")


# ---------------------------------------------------------------- mutations

def _not_json(m):
    return "{this is not json"


def _extra_key(m):
    m["extra"] = "x"
    return m


def _lacks_key(m):
    del m["written_at"]
    return m


def _version_true(m):
    m["version"] = True
    return m


def _short_hash(m):
    m["source_hash"] = "sha256:abc"
    return m


def _owner_upper(m):
    m["owners"] = ["pipeline-team", "Alice"]
    return m


def _pass_partial(m):
    m["characterization"] = {"overall": "pass", "criteria_passed": 1, "criteria_total": 2}
    return m


def _component_bar(m):
    m["component_id"] = "comp-bar"
    return m


def _other_path(m):
    m["source_path"] = "pipeline/other/"
    return m


def _different_hash(m):
    m["source_hash"] = "sha256:" + hashlib.sha256(b"different content entirely").hexdigest()
    return m


def _owners_subset(m):
    m["owners"] = ["pipeline-team"]
    return m


def _owners_reordered(m):
    m["owners"] = ["alice", "pipeline-team"]
    return m


def _old_verifier(m):
    m["verifier_version"] = "verifier-orchestrator@1.0.0"
    return m


def _char_failed(m):
    m["characterization"] = {"overall": "fail", "criteria_passed": 1, "criteria_total": 2}
    return m


SCENARIOS = [
    ("not_json", _not_json, "manifest_invalid"),
    ("extra_key", _extra_key, "manifest_invalid"),
    ("lacks_key", _lacks_key, "manifest_invalid"),
    ("version_true", _version_true, "manifest_invalid"),
    ("short_hash", _short_hash, "manifest_invalid"),
    ("owner_upper", _owner_upper, "manifest_invalid"),
    ("pass_partial", _pass_partial, "manifest_invalid"),
    ("component_bar", _component_bar, "component_mismatch"),
    ("other_path", _other_path, "component_mismatch"),
    ("different_hash", _different_hash, "source_changed"),
    ("owners_subset", _owners_subset, "owners_changed"),
    ("owners_reordered", _owners_reordered, "owners_changed"),
    ("old_verifier", _old_verifier, "verifier_changed"),
    ("char_failed", _char_failed, "characterization_failed"),
]


@pytest.mark.parametrize("name,mutate,reason", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_manifest_miss_reasons(tmp_path, name, mutate, reason):
    repo_root = build_repo(tmp_path)
    source_hash = current_hash(repo_root)
    content = mutate(copy.deepcopy(valid_manifest(source_hash)))
    text = content if isinstance(content, str) else json.dumps(content)
    manifest_path(repo_root).write_text(text, encoding="utf-8")

    result = run_check(repo_root)

    assert_miss(result, reason)


# ---------------------------------------------------------------- not sealed

def test_not_sealed(tmp_path):
    repo_root = build_repo(tmp_path, sealed=False)
    assert provenance_checker.current_sealed_key(COMPONENT_ID, repo_root) is None
    manifest_path(repo_root).write_text(json.dumps(valid_manifest(DUMMY_HASH)), encoding="utf-8")

    result = run_check(repo_root)

    assert_miss(result, "not_sealed", sealed=False)