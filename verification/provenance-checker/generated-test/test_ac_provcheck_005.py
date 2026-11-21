# hotdocs-criterion: sha256:ecdb62ad336ac033edb00ede3443c43d65e804d2f82944fbda0227ffaceb391b
import hashlib
import json
import os
from pathlib import Path

import provenance_checker


PK = "sha256:" + "a" * 64
H = "sha256:" + hashlib.sha256(b"AC-PROVCHECK-005 bundle").hexdigest()


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_python_adapter(repo_root):
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    source = (
        "KIND = " + repr("python") + "\n"
        "\n"
        "\n"
        "def guidance():\n"
        "    return " + repr({"generator": "", "test_author": ""}) + "\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return " + repr(provision_result) + "\n"
    )
    path = adapter_dir / "kind_python.py"
    path.write_text(source, encoding="utf-8")
    return path


def _write_component_md(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    text = (
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
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def _build_repo(repo_root):
    adapter_path = _write_python_adapter(repo_root)
    _write_component_md(repo_root)
    pa = "sha256:" + hashlib.sha256(adapter_path.read_bytes()).hexdigest()
    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    verification_report = {
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "llm-judge",
                "result": "pass",
                "rationale": "looks right",
            }
        ]
    }
    manifest = {
        "spec_bundle_hash": H,
        "gate_versions": {},
        "verification_report": verification_report,
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
    }
    gen_foo = repo_root / "gen" / "foo"
    gen_foo.mkdir(parents=True, exist_ok=True)
    (gen_foo / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_llm_judge_hash_match_is_hit_when_judge_provenance_trusted(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    monkeypatch.setenv("VAR_TRUST_JUDGE_PROVENANCE", "true")
    try:
        result = provenance_checker.check_provenance("comp-foo", H, {}, repo_root)
    finally:
        monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)

    assert "VAR_TRUST_JUDGE_PROVENANCE" not in os.environ
    assert field(result, "hit") is True