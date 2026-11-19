# hotdocs-criterion: sha256:e17d16d6613ff2bacebf56cacbe20a13a7d50a5bd64b6fdade61be67f6239572
import os
import stat
from pathlib import Path

import pytest

import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_fake_node(directory, printed):
    directory.mkdir(parents=True, exist_ok=True)
    node = directory / "node"
    source = "#!/bin/sh\n" + "printf '%s\\n' " + "'" + printed + "'" + "\n"
    node.write_text(source, encoding="utf-8")
    node.chmod(node.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return directory


EXPECTED_MISSING = {
    "ok": False,
    "reason": "javascript needs node >= 24",
    "versions": {},
    "lockfile_sha256": None,
}


def test_ac_kjs_009_missing_or_old_node(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    empty_dir = tmp_path / "empty_bin"
    empty_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))

    result = kind_javascript.provision(repo_root)
    assert dict(result) == EXPECTED_MISSING
    assert list(os.listdir(repo_root)) == []

    asset = tmp_path / "asset.js"
    asset.write_text("export function f() { return 1; }\n", encoding="utf-8")
    with pytest.raises(kind_javascript.AssetError) as excinfo:
        kind_javascript.asset_runner(asset)("f", [])
    assert str(excinfo.value) == "javascript needs node >= 24"

    old_dir = make_fake_node(tmp_path / "old_bin", "v18.2.0")
    monkeypatch.setenv("PATH", str(old_dir))
    result_old = kind_javascript.provision(repo_root)
    assert dict(result_old) == EXPECTED_MISSING

    hello_dir = make_fake_node(tmp_path / "hello_bin", "hello")
    monkeypatch.setenv("PATH", str(hello_dir))
    result_hello = kind_javascript.provision(repo_root)
    assert field(result_hello, "ok") is False
    assert field(result_hello, "versions") == {}
    assert (
        field(result_hello, "reason")
        == "javascript environment: node --version printed hello"
    )