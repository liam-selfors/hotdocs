# hotdocs-criterion: sha256:609f61d20e5267f7469d9556e2e8f4eb17c86835f77b590be61b26a3285968ac
import shutil

import pytest

import kind_javascript
from kind_javascript import AssetError, asset_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _node_ok(tmp_path):
    if shutil.which("node") is None:
        return False
    result = kind_javascript.provision(tmp_path)
    return bool(field(result, "ok"))


def test_ac_kjs_007_restricted_env_and_fs_and_copy_at_call_time(tmp_path, monkeypatch):
    if not _node_ok(tmp_path):
        pytest.skip("node >= 24 not available")

    secret = tmp_path / "secret.txt"
    secret.write_text("s3cret", encoding="utf-8")

    asset = tmp_path / "m.js"
    asset.write_text(
        "import { readFileSync } from 'node:fs';\n"
        "export function home() { return process.env.HOME ?? null; }\n"
        "export function peek(p) { return readFileSync(p, 'utf8'); }\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", "/home/x")

    run = asset_runner(asset)
    assert callable(run)

    # Only PATH reaches the process.
    assert run("home", []) is None

    # The asset may read no file but its copy and the driver.
    with pytest.raises(AssetError, match="restricted"):
        run("peek", [str(secret)])

    # The file is copied at call time.
    asset.write_text(
        "export function home() { return 'new'; }\n",
        encoding="utf-8",
    )
    assert run("home", []) == "new"