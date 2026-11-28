# hotdocs-criterion: sha256:f07abc634a1bb4d7ad549868056900723e44d34c43fe1a2d39af91f4a86ae503
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


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # The fake python adapter (test spec: "The fake python adapter").
    provision_result = {
        "ok": True,
        "reason": "",
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
        "interpreter": "/fake/python",
    }
    kind_python_src = (
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
    kind_python = _write(
        repo_root / "gen" / "kind-python" / "kind_python.py", kind_python_src
    )

    # component.md for comp-foo, with no assets line.
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
    _write(repo_root / "specs" / "components" / "foo" / "component.md", component_md)

    python_entry = {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": _sha256_file(kind_python),
        "versions": {"python": "3.12.4", "packages": PK},
        "lockfile_sha256": None,
    }

    manifest = {
        "spec_bundle_hash": "sha256:0a1b",
        "gate_versions": {"license_scanner": "1"},
        "verification_report": {"criteria": [], "overall": "pass"},
        "license_scan": {},
        "secret_scan": {},
        "assets": [python_entry],
        "drivers": [],
    }
    _write(repo_root / "gen" / "foo" / ".provenance.json", json.dumps(manifest, indent=2))
    return repo_root


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    root = _build_repo(tmp_path)
    monkeypatch.chdir(root)
    return root


def test_json_equals_form_reports_hit(repo_root, capsys):
    code = provenance_checker.main(
        [
            "check",
            "comp-foo",
            "--spec-bundle-hash=sha256:0a1b",
            "--gate-versions=" + GATE_VERSIONS_JSON,
            "--repo-root=" + str(repo_root),
            "--format=json",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    result = json.loads(out)
    assert field(result, "hit") is True


def test_text_space_form_reports_miss(repo_root, capsys):
    code = provenance_checker.main(
        [
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
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "miss" in out


def _usage_cases(repo_root):
    rr = "--repo-root=" + str(repo_root)
    good_hash = "--spec-bundle-hash=sha256:0a1b"
    good_gates = "--gate-versions=" + GATE_VERSIONS_JSON
    return {
        "missing-spec-bundle-hash": ["check", "comp-foo", good_gates, rr],
        "hash-without-prefix": [
            "check", "comp-foo", "--spec-bundle-hash=0a1b", good_gates, rr,
        ],
        "gate-versions-not-object": [
            "check", "comp-foo", good_hash, "--gate-versions", "[1]", rr,
        ],
        "bogus-format": [
            "check", "comp-foo", good_hash, good_gates, rr, "--format=bogus",
        ],
        "unknown-argument": [
            "check", "comp-foo", good_hash, good_gates, rr, "--hotdocs-smoke-unknown",
        ],
        "repo-root-last-without-value": [
            "check", "comp-foo", good_hash, good_gates, "--repo-root",
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
        "repo-root-last-without-value",
    ],
)
def test_usage_errors_return_2(repo_root, capsys, case):
    argv = _usage_cases(repo_root)[case]
    code = provenance_checker.main(argv)
    capsys.readouterr()
    assert code == 2