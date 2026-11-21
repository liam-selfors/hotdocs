# hotdocs-criterion: sha256:b8d76f22bfb1e756d67387716b14576075da8ed88b0391c729b80c1f43548557
import os
import stat

import pytest

import kind_javascript


NEEDS = "javascript needs node >= 24"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_fake_node(directory, line):
    directory.mkdir(parents=True, exist_ok=True)
    node = directory / "node"
    node.write_text("#!/bin/sh\necho " + line + "\n", encoding="utf-8")
    os.chmod(node, 0o755)
    return directory


def expected_needs():
    return {
        "ok": False,
        "reason": NEEDS,
        "versions": {},
        "lockfile_sha256": None,
    }


def test_no_node_on_path(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))

    result = kind_javascript.provision(repo_root)
    assert result == expected_needs()


def test_asset_runner_without_node_raises(tmp_path, monkeypatch):
    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()
    asset = tmp_path / "asset" / "app.js"
    asset.parent.mkdir()
    asset.write_text("export function f() { return 1; }\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(empty_dir))

    with pytest.raises(kind_javascript.AssetError) as excinfo:
        run = kind_javascript.asset_runner(asset)
        run("f", [])
    assert str(excinfo.value) == NEEDS


def test_old_node_gives_same_result(tmp_path, monkeypatch):
    bin_dir = make_fake_node(tmp_path / "fake_bin", "v18.2.0")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))

    result = kind_javascript.provision(repo_root)
    assert result == expected_needs()


def test_unparseable_version_output(tmp_path, monkeypatch):
    bin_dir = make_fake_node(tmp_path / "fake_bin", "hello")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))

    result = kind_javascript.provision(repo_root)
    assert field(result, "ok") is False
    assert field(result, "versions") == {}
    assert field(result, "reason") == (
        "javascript environment: node --version printed hello"
    )