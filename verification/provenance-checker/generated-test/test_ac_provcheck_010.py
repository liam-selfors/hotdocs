# hotdocs-criterion: sha256:71a2b06b975e7e351c14dc02f60410c0aa4b3fd06dd356013315d2709e215c3f
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64
GATE_VERSIONS_JSON = json.dumps({"license_scanner": "1"})


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def _write_manifest(repo_root, python_entry):
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_bundle_hash": "sha256:0a1b",
        "gate_versions": {"license_scanner": "1"},
        "verification_report": {
            "component_id": "comp-foo",
            "criteria": [
                {
                    "id": "AC-FOO-001",
                    "covers": "R-FOO-001",
                    "kind": "generated-test",
                    "result": "pass",
                }
            ],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 1.0,
            "mutation_error": None,
            "assets": [python_entry],
            "overall": "pass",
        },
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
    }
    (gen_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    adapter_path = _write_python_adapter(root)
    _write_component_md(root)
    pa = _sha256_file(adapter_path)
    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }
    _write_manifest(root, python_entry)
    monkeypatch.delenv("VAR_TRUST_JUDGE_PROVENANCE", raising=False)
    monkeypatch.chdir(root)
    return root


def test_json_equals_form_reports_hit(repo_root, capsys):
    argv = [
        "check",
        "comp-foo",
        "--spec-bundle-hash=sha256:0a1b",
        "--gate-versions=" + GATE_VERSIONS_JSON,
        "--repo-root=" + str(repo_root),
        "--format=json",
    ]
    code = provenance_checker.main(argv)
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    assert field(doc, "hit") is True


def test_text_separate_form_reports_miss(repo_root, capsys):
    argv = [
        "check",
        "comp-foo",
        "--spec-bundle-hash",
        "sha256:ffff",
        "--gate-versions",
        GATE_VERSIONS_JSON,
        "--repo-root",
        str(repo_root),
        "--format",
        "text",
    ]
    code = provenance_checker.main(argv)
    out = capsys.readouterr().out
    assert code == 0
    assert "miss" in out


def _usage_cases(root):
    r = str(root)
    return {
        "missing-spec-bundle-hash": [
            "check", "comp-foo",
            "--gate-versions=" + GATE_VERSIONS_JSON,
            "--repo-root=" + r,
            "--format=json",
        ],
        "hash-without-prefix": [
            "check", "comp-foo",
            "--spec-bundle-hash=0a1b",
            "--gate-versions=" + GATE_VERSIONS_JSON,
            "--repo-root=" + r,
            "--format=json",
        ],
        "gate-versions-not-object": [
            "check", "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions", "[1]",
            "--repo-root=" + r,
            "--format=json",
        ],
        "bogus-format": [
            "check", "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions=" + GATE_VERSIONS_JSON,
            "--repo-root=" + r,
            "--format=bogus",
        ],
        "unknown-argument": [
            "check", "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions=" + GATE_VERSIONS_JSON,
            "--repo-root=" + r,
            "--format=json",
            "--hotdocs-smoke-unknown",
        ],
        "repo-root-last-no-value": [
            "check", "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions=" + GATE_VERSIONS_JSON,
            "--format=json",
            "--repo-root",
        ],
    }


@pytest.mark.parametrize(
    "case",
    [
        "missing-spec-bundle-hash",
        "hash-without-prefix",
        "gate-versions-not-object",
        "bogus-format",
        "unknown-argument",
        "repo-root-last-no-value",
    ],
)
def test_usage_errors_return_2(repo_root, capsys, case):
    argv = _usage_cases(repo_root)[case]
    code = provenance_checker.main(argv)
    capsys.readouterr()
    assert code == 2