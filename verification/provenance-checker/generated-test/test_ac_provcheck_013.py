"""AC-PROVCHECK-013 (Covers: R-PROVCHECK-008).

A manifest that is not a valid SealedProvenance document yields reason
"manifest_invalid". A valid manifest whose characterization failed yields
"characterization_failed". A component that is not sealed yields
"not_sealed" with sealed false; every other reason (and a hit) has sealed
true.
"""

import json
from pathlib import Path

import pytest

import provenance_checker


COMPONENT_ID = "comp-foo"
SOURCE_PATH = "legacy/foo/"
VERIFIER_VERSION = "verifier-orchestrator@2.0.0"
WRITTEN_AT = "2026-11-02T00:00:00Z"
BASE_CHARACTERIZATION = {"overall": "pass", "criteria_passed": 2, "criteria_total": 2}

HEX64 = "0123456789abcdef" * 4
HEX64_UPPER = "0123456789ABCDEF" * 4


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


FOO_COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

BAR_COMPONENT_MD = (
    "---\n"
    "id: comp-bar\n"
    "title: Bar\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Bar\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Bar triples a number.\n"
)

FAKE_VERIFIER = (
    "GATE_VERSION = \"verifier-orchestrator@2.0.0\"\n"
    "\n"
    "\n"
    "class _Report:\n"
    "    def __init__(self, component_id):\n"
    "        self.component_id = component_id\n"
    "        self.criteria = []\n"
    "        self.requirement_results = {}\n"
    "        self.interface_drift = False\n"
    "        self.mutation_score = None\n"
    "        self.overall = \"pass\"\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {\n"
    "            \"component_id\": self.component_id,\n"
    "            \"criteria\": list(self.criteria),\n"
    "            \"requirement_results\": dict(self.requirement_results),\n"
    "            \"interface_drift\": self.interface_drift,\n"
    "            \"mutation_score\": self.mutation_score,\n"
    "            \"overall\": self.overall,\n"
    "        }\n"
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    return _Report(component_id)\n"
)


def _write_component_units(base: Path, prefix: str, fn: str) -> None:
    _write(
        base / "requirements" / f"R-{prefix}-001.md",
        f"# R-{prefix}-001\n\n**R-{prefix}-001** — `{fn}(x)` MUST return `2 * x`.\n",
    )
    _write(
        base / "acceptance" / f"AC-{prefix}-001.md",
        f"# AC-{prefix}-001\n"
        "\n"
        f"Covers: R-{prefix}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        f"When {fn}(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        base / "interface" / "library.md",
        f"# Library\n\n```\n{fn}(x: int) -> int\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")


def _build_repo(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")

    foo = repo_root / "specs" / "components" / "foo"
    _write(foo / "component.md", FOO_COMPONENT_MD)
    _write_component_units(foo, "FOO", "foo")

    bar = repo_root / "specs" / "components" / "bar"
    _write(bar / "component.md", BAR_COMPONENT_MD)
    _write_component_units(bar, "BAR", "bar")

    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")

    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        FAKE_VERIFIER,
    )


def _manifest_path(repo_root: Path) -> Path:
    return repo_root / "legacy" / "foo" / ".sealed-provenance.json"


@pytest.fixture
def sealed_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    key = provenance_checker.current_sealed_key(COMPONENT_ID, repo_root)
    assert key is not None, "comp-foo is sealed; current_sealed_key must not return None"
    assert list(field(key, "owners")) == ["pipeline-team"]
    assert field(key, "source_path") == SOURCE_PATH
    assert field(key, "verifier_version") == VERIFIER_VERSION

    base = {
        "kind": "sealed-provenance",
        "version": 1,
        "component_id": COMPONENT_ID,
        "owners": list(field(key, "owners")),
        "source_path": field(key, "source_path"),
        "source_hash": field(key, "source_hash"),
        "verifier_version": field(key, "verifier_version"),
        "characterization": dict(BASE_CHARACTERIZATION),
        "written_at": WRITTEN_AT,
    }
    return repo_root, base


def _check_with(repo_root: Path, document_text: str):
    _write(_manifest_path(repo_root), document_text)
    return provenance_checker.check_sealed_provenance(COMPONENT_ID, repo_root)


def _assert_miss(result, reason):
    assert field(result, "reason") == reason
    assert field(result, "hit") is False
    assert field(result, "sealed") is True
    for name in ("verification_report", "owners", "source_hash", "written_at"):
        assert field(result, name) is None, f"{name} must be null on a miss"
    assert field(result, "license_scan") is None
    assert field(result, "secret_scan") is None


def test_baseline_valid_current_manifest_is_a_hit(sealed_repo):
    repo_root, base = sealed_repo
    result = _check_with(repo_root, json.dumps(base))
    assert field(result, "reason") is None
    assert field(result, "hit") is True
    assert field(result, "sealed") is True


@pytest.mark.parametrize(
    "document_text",
    [json.dumps([1, 2, 3]), json.dumps(5), json.dumps("sealed-provenance"), "null"],
    ids=["list", "number", "string", "null"],
)
def test_non_object_manifest_is_invalid(sealed_repo, document_text):
    repo_root, _ = sealed_repo
    result = _check_with(repo_root, document_text)
    _assert_miss(result, "manifest_invalid")


TOP_LEVEL_MUTATIONS = [
    ("kind", "sealed"),
    ("kind", 5),
    ("version", 2),
    ("version", "1"),
    ("version", 1.0),
    ("component_id", 5),
    ("component_id", "Comp-foo"),
    ("component_id", "foo"),
    ("owners", "pipeline-team"),
    ("owners", []),
    ("owners", [5]),
    ("owners", ["pipeline-team", ""]),
    ("owners", ["Pipeline"]),
    ("source_path", 5),
    ("source_path", "../x/"),
    ("source_path", "gen/foo/"),
    ("source_path", "/abs/"),
    ("source_path", "a b/"),
    ("source_hash", 5),
    ("source_hash", "sha256:" + HEX64[:63]),
    ("source_hash", "sha256:" + HEX64_UPPER),
    ("source_hash", "sha1:" + HEX64),
    ("verifier_version", 5),
    ("verifier_version", "verifier-orchestrator@2"),
    ("verifier_version", "other@2.0.0"),
    ("written_at", 5),
    ("written_at", "2026-11-02"),
    ("written_at", "2026-11-02 00:00:00Z"),
    ("written_at", "2026-11-02T00:00:00"),
]


@pytest.mark.parametrize(
    "key,value",
    TOP_LEVEL_MUTATIONS,
    ids=[f"{k}={v!r}" for k, v in TOP_LEVEL_MUTATIONS],
)
def test_top_level_field_change_is_invalid(sealed_repo, key, value):
    repo_root, base = sealed_repo
    doc = dict(base)
    doc[key] = value
    result = _check_with(repo_root, json.dumps(doc))
    _assert_miss(result, "manifest_invalid")


CHARACTERIZATION_MUTATIONS = [
    ("list", ["pass", 2, 2]),
    ("missing_total", {"overall": "pass", "criteria_passed": 2}),
    ("extra_key", {**BASE_CHARACTERIZATION, "extra": 1}),
    ("overall_ok", {**BASE_CHARACTERIZATION, "overall": "ok"}),
    ("overall_5", {**BASE_CHARACTERIZATION, "overall": 5}),
    ("passed_str", {**BASE_CHARACTERIZATION, "criteria_passed": "2"}),
    ("passed_true", {**BASE_CHARACTERIZATION, "criteria_passed": True}),
    ("total_neg", {**BASE_CHARACTERIZATION, "criteria_total": -1}),
    ("passed_gt_total", {"overall": "pass", "criteria_passed": 3, "criteria_total": 2}),
    ("pass_zero_zero", {"overall": "pass", "criteria_passed": 0, "criteria_total": 0}),
]


@pytest.mark.parametrize(
    "characterization",
    [c for _, c in CHARACTERIZATION_MUTATIONS],
    ids=[name for name, _ in CHARACTERIZATION_MUTATIONS],
)
def test_characterization_change_is_invalid(sealed_repo, characterization):
    repo_root, base = sealed_repo
    doc = dict(base)
    doc["characterization"] = characterization
    result = _check_with(repo_root, json.dumps(doc))
    _assert_miss(result, "manifest_invalid")


@pytest.mark.parametrize(
    "characterization",
    [
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 2},
        {"overall": "fail", "criteria_passed": 0, "criteria_total": 0},
    ],
    ids=["fail_0_of_2", "fail_0_of_0"],
)
def test_failed_characterization_is_valid_but_failed(sealed_repo, characterization):
    repo_root, base = sealed_repo
    doc = dict(base)
    doc["characterization"] = characterization
    result = _check_with(repo_root, json.dumps(doc))
    _assert_miss(result, "characterization_failed")


def test_not_sealed_component_reports_not_sealed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    assert provenance_checker.current_sealed_key("comp-bar", repo_root) is None

    result = provenance_checker.check_sealed_provenance("comp-bar", repo_root)
    assert field(result, "reason") == "not_sealed"
    assert field(result, "sealed") is False
    assert field(result, "hit") is False
    for name in ("verification_report", "owners", "source_hash", "written_at"):
        assert field(result, name) is None


def _other_hash(current: str) -> str:
    candidate = "sha256:" + "f" * 64
    if candidate == current:
        candidate = "sha256:" + "e" * 64
    return candidate


@pytest.mark.parametrize(
    "reason",
    [
        "manifest_missing",
        "component_mismatch",
        "source_changed",
        "owners_changed",
        "verifier_changed",
    ],
)
def test_every_other_reason_reports_sealed_true(sealed_repo, reason):
    repo_root, base = sealed_repo
    doc = dict(base)
    if reason == "manifest_missing":
        path = _manifest_path(repo_root)
        if path.exists():
            path.unlink()
        result = provenance_checker.check_sealed_provenance(COMPONENT_ID, repo_root)
    else:
        if reason == "component_mismatch":
            doc["component_id"] = "comp-other"
        elif reason == "source_changed":
            doc["source_hash"] = _other_hash(base["source_hash"])
        elif reason == "owners_changed":
            doc["owners"] = ["other-team"]
        elif reason == "verifier_changed":
            doc["verifier_version"] = "verifier-orchestrator@9.9.9"
        result = _check_with(repo_root, json.dumps(doc))
    _assert_miss(result, reason)