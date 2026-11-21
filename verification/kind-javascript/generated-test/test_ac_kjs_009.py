# hotdocs-criterion: sha256:be65a515f8a3615f8224d83d98234f1d648c76a836b91063b5e707ce7edf6f2e
import os

import pytest

import kind_javascript


NEEDS = "javascript needs node >= 24"
EXPECTED_NO_NODE = {
    "ok": False,
    "reason": NEEDS,
    "versions": {},
    "lockfile_sha256": None,
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(value):
    if isinstance(value, dict):
        return dict(value)
    return {
        "ok": field(value, "ok"),
        "reason": field(value, "reason"),
        "versions": field(value, "versions"),
        "lockfile_sha256": field(value, "lockfile_sha256"),
    }


def make_fake_node(directory, line):
    directory.mkdir(parents=True, exist_ok=True)
    node = directory / "node"
    node.write_text("#!/bin/sh\necho " + line + "\n", encoding="utf-8")
    os.chmod(node, 0o755)
    return directory


def test_no_node_on_path(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    result = kind_javascript.provision(repo_root)
    assert isinstance(result, dict)
    assert result == EXPECTED_NO_NODE

    asset = tmp_path / "app.js"
    asset.write_text(
        "export function f() {\n  return 1;\n}\n", encoding="utf-8"
    )
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        kind_javascript.asset_runner(asset)("f", [])
    assert str(excinfo.value) == NEEDS


def test_old_node_on_path(tmp_path, monkeypatch):
    fake_dir = make_fake_node(tmp_path / "fake_bin", "v18.2.0")
    monkeypatch.setenv("PATH", str(fake_dir))

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    result = kind_javascript.provision(repo_root)
    assert isinstance(result, dict)
    assert result == EXPECTED_NO_NODE


def test_unparseable_node_version(tmp_path, monkeypatch):
    fake_dir = make_fake_node(tmp_path / "fake_bin", "hello")
    monkeypatch.setenv("PATH", str(fake_dir))

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    result = kind_javascript.provision(repo_root)
    assert field(result, "ok") is False
    assert field(result, "versions") == {}
    assert (
        field(result, "reason")
        == "javascript environment: node --version printed hello"
    )