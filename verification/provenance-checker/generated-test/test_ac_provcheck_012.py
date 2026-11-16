import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


OWNERS = ["pipeline-team", "alice"]
SOURCE_PATH = "pipeline/foo/"
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
WRITTEN_AT = "2026-11-02T00:00:00Z"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _component_md(sealed: bool) -> str:
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team, alice]",
    ]
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: pipeline/foo/")
    else:
        lines.append("sealed: false")
    lines.append("depends_on: []")
    lines.append("---")
    lines.append("")
    lines.append("# Foo")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("Foo doubles a number.")
    lines.append("")
    return "\n".join(lines)


FAKE_VERIFIER = (
    'GATE_VERSION = "verifier-orchestrator@2.0.0"\n'
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    '    raise NotImplementedError("fake verifier-orchestrator: verify not used")\n'
)


def make_repo(root: Path, sealed: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "specs").mkdir(parents=True, exist_ok=True)
    (root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    comp_dir = root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(_component_md(sealed), encoding="utf-8")

    src = root / "pipeline" / "foo"
    src.mkdir(parents=True, exist_ok=True)
    (src / "foo.py").write_text(
        "def double(x):\n    return 2 * x\n", encoding="utf-8"
    )

    vo = root / "gen" / "verifier-orchestrator"
    vo.mkdir(parents=True, exist_ok=True)
    (vo / "verifier_orchestrator.py").write_text(FAKE_VERIFIER, encoding="utf-8")
    return root


def valid_manifest(source_hash: str) -> dict:
    return {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": "comp-foo",
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


def manifest_path(root: Path) -> Path:
    return root / "pipeline" / "foo" / ".sealed-provenance.json"


def snapshot(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if "__pycache__" in rel.parts:
            continue
        if p.is_file():
            out[rel.as_posix()] = ("file", p.read_bytes())
        elif p.is_dir():
            out[rel.as_posix()] = ("dir", None)
        else:
            out[rel.as_posix()] = ("other", None)
    return out


def different_hash(current: str) -> str:
    h = "sha256:" + hashlib.sha256(b"entirely different content").hexdigest()
    if h == current:
        h = "sha256:" + hashlib.sha256(b"yet other content").hexdigest()
    assert h != current
    return h


# Each mutator takes (manifest_dict, current_hash) and returns the text to
# write, or None to write no manifest at all.
def _json(m):
    return json.dumps(m)


def m_valid(m, h):
    return _json(m)


def m_missing(m, h):
    return None


def m_not_json(m, h):
    return "{this is not json"


def m_extra_key(m, h):
    m["extra"] = "x"
    return _json(m)


def m_lacks_key(m, h):
    del m["written_at"]
    return _json(m)


def m_version_true(m, h):
    m["version"] = True
    return _json(m)


def m_short_hash(m, h):
    m["source_hash"] = "sha256:abc"
    return _json(m)


def m_owner_capital(m, h):
    m["owners"] = ["pipeline-team", "Alice"]
    return _json(m)


def m_pass_partial(m, h):
    m["characterization"] = {"overall": "pass", "criteria_passed": 1, "criteria_total": 2}
    return _json(m)


def m_component_bar(m, h):
    m["component_id"] = "comp-bar"
    return _json(m)


def m_other_path(m, h):
    m["source_path"] = "pipeline/other/"
    return _json(m)


def m_source_changed(m, h):
    m["source_hash"] = different_hash(h)
    return _json(m)


def m_owners_subset(m, h):
    m["owners"] = ["pipeline-team"]
    return _json(m)


def m_owners_reordered(m, h):
    m["owners"] = ["alice", "pipeline-team"]
    return _json(m)


def m_verifier_old(m, h):
    m["verifier_version"] = "verifier-orchestrator@1.0.0"
    return _json(m)


def m_char_fail(m, h):
    m["characterization"] = {"overall": "fail", "criteria_passed": 1, "criteria_total": 2}
    return _json(m)


MISS_SCENARIOS = [
    ("missing", m_missing, "manifest_missing"),
    ("not_json", m_not_json, "manifest_invalid"),
    ("extra_key", m_extra_key, "manifest_invalid"),
    ("lacks_key", m_lacks_key, "manifest_invalid"),
    ("version_true", m_version_true, "manifest_invalid"),
    ("short_hash", m_short_hash, "manifest_invalid"),
    ("owner_capital", m_owner_capital, "manifest_invalid"),
    ("pass_partial", m_pass_partial, "manifest_invalid"),
    ("component_bar", m_component_bar, "component_mismatch"),
    ("other_path", m_other_path, "component_mismatch"),
    ("source_changed", m_source_changed, "source_changed"),
    ("owners_subset", m_owners_subset, "owners_changed"),
    ("owners_reordered", m_owners_reordered, "owners_changed"),
    ("verifier_old", m_verifier_old, "verifier_changed"),
    ("characterization_failed", m_char_fail, "characterization_failed"),
]


def _setup_sealed(tmp_path: Path, mutator):
    repo_root = make_repo(tmp_path / "repo", sealed=True)
    key = provenance_checker.current_sealed_key("comp-foo", repo_root)
    assert key is not None
    current_hash = field(key, "source_hash")
    text = mutator(valid_manifest(current_hash), current_hash)
    if text is not None:
        manifest_path(repo_root).write_text(text, encoding="utf-8")
    return repo_root, current_hash


def _vr_overall(vr):
    if isinstance(vr, dict):
        return vr
    return {"overall": getattr(vr, "overall")}


def test_valid_current_manifest_is_a_hit(tmp_path):
    repo_root, current_hash = _setup_sealed(tmp_path, m_valid)
    before = snapshot(repo_root)

    result = provenance_checker.check_sealed_provenance("comp-foo", repo_root)

    assert field(result, "hit") is True
    assert field(result, "reason") is None
    assert field(result, "sealed") is True
    assert _vr_overall(field(result, "verification_report")) == {"overall": "pass"}
    assert list(field(result, "owners")) == OWNERS
    assert field(result, "written_at") == WRITTEN_AT
    assert field(result, "source_hash") == current_hash
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None

    assert snapshot(repo_root) == before


@pytest.mark.parametrize(
    "mutator,expected_reason",
    [(m, r) for _, m, r in MISS_SCENARIOS],
    ids=[i for i, _, _ in MISS_SCENARIOS],
)
def test_sealed_miss_reasons(tmp_path, mutator, expected_reason):
    repo_root, _ = _setup_sealed(tmp_path, mutator)
    before = snapshot(repo_root)

    result = provenance_checker.check_sealed_provenance("comp-foo", repo_root)

    assert field(result, "reason") == expected_reason
    assert field(result, "hit") is False
    assert field(result, "sealed") is True
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None

    assert snapshot(repo_root) == before


def test_not_sealed_component(tmp_path):
    repo_root = make_repo(tmp_path / "repo", sealed=False)
    assert provenance_checker.current_sealed_key("comp-foo", repo_root) is None
    # A manifest lying around does not make an unsealed component sealed.
    manifest_path(repo_root).write_text(
        json.dumps(valid_manifest("sha256:" + "0" * 64)), encoding="utf-8"
    )
    before = snapshot(repo_root)

    result = provenance_checker.check_sealed_provenance("comp-foo", repo_root)

    assert field(result, "reason") == "not_sealed"
    assert field(result, "hit") is False
    assert field(result, "sealed") is False
    assert field(result, "verification_report") is None
    assert field(result, "owners") is None
    assert field(result, "source_hash") is None
    assert field(result, "written_at") is None
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None

    assert snapshot(repo_root) == before