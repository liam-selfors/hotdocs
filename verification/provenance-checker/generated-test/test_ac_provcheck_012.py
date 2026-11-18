# hotdocs-criterion: sha256:d0ea99b23eaaa87aa880cf9c0f7d28486d5b03f4b233ff0301e85ab3911d5fab
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root, sealed=True):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    frontmatter = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team, alice]\n"
    )
    if sealed:
        frontmatter += "sealed: true\n" + "source_path: pipeline/foo/\n"
    frontmatter += "depends_on: []\n" + "---\n"
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        frontmatter + "\n# Foo\n\n## Purpose\n\nFoo doubles a number.\n",
    )
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # Sealed component's real source.
    _write(
        repo_root / "pipeline" / "foo" / "foo.py",
        "def foo(x):\n    return 2 * x\n",
    )

    # Fake verifier-orchestrator, flat-module shape.
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "GATE_VERSION = " + repr(VERIFIER_VERSION) + "\n",
    )


def _valid_manifest(source_hash):
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": COMPONENT_ID,
        "owners": list(OWNERS),
        "source_path": SOURCE_PATH,
        "source_hash": source_hash,
        "verifier_version": VERIFIER_VERSION,
        "characterization": {
            "overall": "pass",
            "criteria_passed": 2,
            "criteria_total": 2,
        },
        "written_at": WRITTEN_AT,
    }


def _snapshot(repo_root):
    snap = {}
    for p in sorted(repo_root.rglob("*")):
        rel = p.relative_to(repo_root)
        if "__pycache__" in rel.parts:
            continue
        if p.is_file():
            snap[str(rel)] = ("file", p.read_bytes())
        elif p.is_dir():
            snap[str(rel)] = ("dir", None)
    return snap


def _different_hash(current):
    candidate = "sha256:" + hashlib.sha256(b"entirely different content").hexdigest()
    if candidate == current:
        candidate = "sha256:" + hashlib.sha256(b"other different content").hexdigest()
    return candidate


# Each mutator takes (manifest_dict, current_source_hash) and returns either
# a dict (to be written as JSON) or a str (written verbatim).
def m_valid(m, h):
    return m


def m_not_json(m, h):
    return "{this is not json"


def m_extra_key(m, h):
    m["extra"] = "x"
    return m


def m_missing_key(m, h):
    del m["written_at"]
    return m


def m_version_true(m, h):
    m["version"] = True
    return m


def m_bad_hash(m, h):
    m["source_hash"] = "sha256:abc"
    return m


def m_bad_owner(m, h):
    m["owners"] = ["pipeline-team", "Alice"]
    return m


def m_pass_partial(m, h):
    m["characterization"] = {"overall": "pass", "criteria_passed": 1, "criteria_total": 2}
    return m


def m_component_bar(m, h):
    m["component_id"] = "comp-bar"
    return m


def m_other_path(m, h):
    m["source_path"] = "pipeline/other/"
    return m


def m_source_changed(m, h):
    m["source_hash"] = _different_hash(h)
    return m


def m_owners_subset(m, h):
    m["owners"] = ["pipeline-team"]
    return m


def m_owners_reordered(m, h):
    m["owners"] = ["alice", "pipeline-team"]
    return m


def m_verifier_old(m, h):
    m["verifier_version"] = "verifier-orchestrator@1.0.0"
    return m


def m_char_fail(m, h):
    m["characterization"] = {"overall": "fail", "criteria_passed": 1, "criteria_total": 2}
    return m


MISS_SCENARIOS = [
    ("not_json", m_not_json, "manifest_invalid"),
    ("extra_key", m_extra_key, "manifest_invalid"),
    ("missing_key", m_missing_key, "manifest_invalid"),
    ("version_true", m_version_true, "manifest_invalid"),
    ("bad_hash", m_bad_hash, "manifest_invalid"),
    ("bad_owner", m_bad_owner, "manifest_invalid"),
    ("pass_partial", m_pass_partial, "manifest_invalid"),
    ("component_bar", m_component_bar, "component_mismatch"),
    ("other_path", m_other_path, "component_mismatch"),
    ("source_changed", m_source_changed, "source_changed"),
    ("owners_subset", m_owners_subset, "owners_changed"),
    ("owners_reordered", m_owners_reordered, "owners_changed"),
    ("verifier_old", m_verifier_old, "verifier_changed"),
    ("char_fail", m_char_fail, "characterization_failed"),
]


def _setup_sealed(tmp_path, mutator):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, sealed=True)
    key = provenance_checker.current_sealed_key(COMPONENT_ID, repo_root)
    assert key is not None
    current_hash = field(key, "source_hash")
    if mutator is not None:
        content = mutator(copy.deepcopy(_valid_manifest(current_hash)), current_hash)
        text = content if isinstance(content, str) else json.dumps(content, indent=2)
        _write(repo_root / "pipeline" / "foo" / ".sealed-provenance.json", text)
    return repo_root, current_hash


def _assert_vr_pass(vr):
    if isinstance(vr, dict):
        assert vr == {"overall": "pass"}
    else:
        assert field(vr, "overall") == "pass"


def test_valid_current_manifest_is_hit(tmp_path):
    repo_root, current_hash = _setup_sealed(tmp_path, m_valid)
    before = _snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo_root)
    after = _snapshot(repo_root)

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "sealed") is True
    _assert_vr_pass(field(result, "verification_report"))
    assert list(field(result, "owners")) == OWNERS
    assert field(result, "written_at") == WRITTEN_AT
    assert field(result, "source_hash") == current_hash
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert before == after


def test_manifest_missing(tmp_path):
    repo_root, _ = _setup_sealed(tmp_path, None)
    before = _snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo_root)
    after = _snapshot(repo_root)

    assert field(result, "reason") == "manifest_missing"
    assert field(result, "hit") is False
    assert field(result, "sealed") is True
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None
    assert before == after


@pytest.mark.parametrize(
    "mutator,expected_reason",
    [(m, r) for (_, m, r) in MISS_SCENARIOS],
    ids=[n for (n, _, _) in MISS_SCENARIOS],
)
def test_stale_or_invalid_manifest_is_miss(tmp_path, mutator, expected_reason):
    repo_root, _ = _setup_sealed(tmp_path, mutator)
    before = _snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo_root)
    after = _snapshot(repo_root)

    assert field(result, "reason") == expected_reason
    assert field(result, "hit") is False
    assert field(result, "sealed") is True
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None
    assert before == after


def test_not_sealed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, sealed=False)
    # A manifest present anyway must not matter for an unsealed component.
    manifest = _valid_manifest("sha256:" + hashlib.sha256(b"x").hexdigest())
    _write(
        repo_root / "pipeline" / "foo" / ".sealed-provenance.json",
        json.dumps(manifest, indent=2),
    )
    before = _snapshot(repo_root)
    result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo_root)
    after = _snapshot(repo_root)

    assert field(result, "reason") == "not_sealed"
    assert field(result, "hit") is False
    assert field(result, "sealed") is False
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None
    assert before == after