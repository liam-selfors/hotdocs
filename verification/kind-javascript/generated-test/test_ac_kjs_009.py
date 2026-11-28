# hotdocs-criterion: sha256:be3e1c53af22c629b0e762e2ce9d0cc4513c4c781a16c4854550d0811b21b374
import os
from pathlib import Path

import pytest

import kind_javascript


EXPECTED_NEEDS = {
    "ok": False,
    "reason": "javascript needs node >= 24",
    "versions": {},
    "lockfile_sha256": None,
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_fake_node(directory, line):
    directory.mkdir(parents=True, exist_ok=True)
    node = directory / "node"
    node.write_text("#!/bin/sh\necho " + line + "\n", encoding="utf-8")
    os.chmod(node, 0o755)
    return directory


def test_no_node_on_path_provision_reports_needs_node(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))

    result = kind_javascript.provision(repo_root)

    assert isinstance(result, dict)
    assert result == EXPECTED_NEEDS


def test_no_node_on_path_asset_runner_raises_asset_error(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    asset = tmp_path / "app.js"
    asset.write_text("export function f() { return 1; }\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(empty_dir))

    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run = kind_javascript.asset_runner(asset)
        run("f", [])

    assert str(excinfo.value) == "javascript needs node >= 24"


def test_old_fake_node_provision_reports_needs_node(tmp_path, monkeypatch):
    fake_dir = make_fake_node(tmp_path / "fakebin", "v18.2.0")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("PATH", str(fake_dir))

    result = kind_javascript.provision(repo_root)

    assert isinstance(result, dict)
    assert result == EXPECTED_NEEDS


def test_fake_node_printing_garbage_reports_printed_output(tmp_path, monkeypatch):
    fake_dir = make_fake_node(tmp_path / "fakebin", "hello")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("PATH", str(fake_dir))

    result = kind_javascript.provision(repo_root)

    assert field(result, "ok") is False
    assert field(result, "versions") == {}
    assert field(result, "reason") == (
        "javascript environment: node --version printed hello"
    )
    assert field(result, "lockfile_sha256") is None