# hotdocs-criterion: sha256:b93dc59e220f34fab68fb84efb8bfa16885ebb962ae6cf34c7bae93c2603e58f
import hashlib
import json
from pathlib import Path

import pytest

import provenance_checker


PK = "sha256:" + "a" * 64
GATE_VERSIONS = {"license_scanner": "1"}
GATE_VERSIONS_JSON = json.dumps(GATE_VERSIONS)
SPEC_BUNDLE_HASH = "sha256:0a1b"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _sha256_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_repo(root):
    root = Path(root)

    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    adapter_src = (
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
    adapter_path = _write(root / "gen" / "kind-python" / "kind_python.py", adapter_src)

    component_md = (
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
    _write(root / "specs" / "components" / "foo" / "component.md", component_md)

    pa = _sha256_file(adapter_path)
    p_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": pa,
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    verification_report = {
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
        "assets": [p_entry],
        "drivers": [],
        "overall": "pass",
    }

    manifest = {
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "gate_versions": GATE_VERSIONS,
        "provenance_hit": False,
        "generated_at": "2026-01-01T00:00:00Z",
        "verification_report": verification_report,
        "license_scan": {},
        "secret_scan": {},
        "assets": [p_entry],
        "drivers": [],
    }
    text = json.dumps(manifest, indent=2)
    _write(root / "gen" / "foo" / ".provenance.json", text)
    _write(root / "verification" / "foo" / ".provenance.json", text)
    return root


def test_json_hit_with_equals_form(tmp_path, capsys):
    repo_root = build_repo(tmp_path / "repo")
    argv = [
        "check",
        "comp-foo",
        "--spec-bundle-hash=" + SPEC_BUNDLE_HASH,
        "--gate-versions=" + GATE_VERSIONS_JSON,
        "--repo-root=" + str(repo_root),
        "--format=json",
    ]
    code = provenance_checker.main(argv)
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    assert field(doc, "hit") is True


def test_text_miss_with_separate_value_form(tmp_path, capsys):
    repo_root = build_repo(tmp_path / "repo")
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


def _usage_cases(repo_root):
    rr = "--repo-root=" + str(repo_root)
    return {
        "missing-spec-bundle-hash": [
            "check", "comp-foo", "--gate-versions=" + GATE_VERSIONS_JSON, rr,
        ],
        "hash-without-prefix": [
            "check", "comp-foo", "--spec-bundle-hash=0a1b",
            "--gate-versions=" + GATE_VERSIONS_JSON, rr,
        ],
        "gate-versions-not-object": [
            "check", "comp-foo", "--spec-bundle-hash=" + SPEC_BUNDLE_HASH,
            "--gate-versions", "[1]", rr,
        ],
        "bogus-format": [
            "check", "comp-foo", "--spec-bundle-hash=" + SPEC_BUNDLE_HASH,
            "--gate-versions=" + GATE_VERSIONS_JSON, rr, "--format=bogus",
        ],
        "unknown-argument": [
            "check", "comp-foo", "--spec-bundle-hash=" + SPEC_BUNDLE_HASH,
            "--gate-versions=" + GATE_VERSIONS_JSON, rr, "--hotdocs-smoke-unknown",
        ],
        "repo-root-last-no-value": [
            "check", "comp-foo", "--spec-bundle-hash=" + SPEC_BUNDLE_HASH,
            "--gate-versions=" + GATE_VERSIONS_JSON, "--repo-root",
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
def test_usage_errors_return_2(tmp_path, capsys, case):
    repo_root = build_repo(tmp_path / "repo")
    argv = _usage_cases(repo_root)[case]
    code = provenance_checker.main(argv)
    capsys.readouterr()
    assert code == 2