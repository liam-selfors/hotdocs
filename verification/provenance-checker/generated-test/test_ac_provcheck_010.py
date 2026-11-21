# hotdocs-criterion: sha256:31aee153d4c55e2818e6a00885b59536158faa05ffd3953db6ea2f522f157c46
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _build_repo(root):
    root = Path(root)
    # Fake python adapter
    adapter_dir = root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    provision_value = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    adapter_src = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_value) + "\n"
    )
    adapter_path = adapter_dir / "kind_python.py"
    adapter_path.write_text(adapter_src, encoding="utf-8")
    pa = _sha(adapter_path)

    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    # Component spec (no assets line, not sealed)
    comp_dir = root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    comp_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
    )
    (comp_dir / "component.md").write_text(comp_md, encoding="utf-8")

    # Manifest
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [p_entry],
        "overall": "pass",
    }
    manifest = {
        "spec_bundle_hash": "sha256:0a1b",
        "gate_versions": {"license_scanner": "1"},
        "verification_report": verification_report,
        "license_scan": {},
        "secret_scan": {},
        "assets": [p_entry],
    }
    text = json.dumps(manifest, indent=2)
    for sub in ("gen", "verification"):
        d = root / sub / "foo"
        d.mkdir(parents=True, exist_ok=True)
        (d / ".provenance.json").write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    _build_repo(root)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    return root


def test_json_hit_with_equals_form(repo_root, capsys):
    rc = provenance_checker.main([
        "check",
        "comp-foo",
        "--spec-bundle-hash=sha256:0a1b",
        "--gate-versions=" + json.dumps({"license_scanner": "1"}),
        "--repo-root=" + str(repo_root),
        "--format=json",
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    doc = json.loads(captured.out)
    assert field(doc, "hit") is True


def test_text_miss_with_separate_value_form(repo_root, capsys):
    rc = provenance_checker.main([
        "check",
        "comp-foo",
        "--spec-bundle-hash",
        "sha256:ffff",
        "--gate-versions",
        json.dumps({"license_scanner": "1"}),
        "--repo-root",
        str(repo_root),
        "--format",
        "text",
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert "miss" in captured.out


def _usage_cases(repo_root):
    gv = "--gate-versions=" + json.dumps({"license_scanner": "1"})
    rr = "--repo-root=" + str(repo_root)
    return {
        "missing_spec_bundle_hash": [
            "check", "comp-foo", gv, rr, "--format=json",
        ],
        "hash_without_prefix": [
            "check", "comp-foo", "--spec-bundle-hash=0a1b", gv, rr, "--format=json",
        ],
        "gate_versions_not_object": [
            "check", "comp-foo", "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions", "[1]", rr, "--format=json",
        ],
        "bogus_format": [
            "check", "comp-foo", "--spec-bundle-hash=sha256:0a1b", gv, rr,
            "--format=bogus",
        ],
        "unknown_argument": [
            "check", "comp-foo", "--spec-bundle-hash=sha256:0a1b", gv, rr,
            "--format=json", "--hotdocs-smoke-unknown",
        ],
        "repo_root_last_without_value": [
            "check", "comp-foo", "--spec-bundle-hash=sha256:0a1b", gv,
            "--format=json", "--repo-root",
        ],
    }


@pytest.mark.parametrize("case", [
    "missing_spec_bundle_hash",
    "hash_without_prefix",
    "gate_versions_not_object",
    "bogus_format",
    "unknown_argument",
    "repo_root_last_without_value",
])
def test_usage_errors_return_2(repo_root, capsys, case):
    argv = _usage_cases(repo_root)[case]
    rc = provenance_checker.main(argv)
    capsys.readouterr()
    assert rc == 2