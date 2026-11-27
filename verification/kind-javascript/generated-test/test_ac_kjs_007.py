# hotdocs-criterion: sha256:97f1c19ab3b880fe9e518cf4516aec188f115c874fe4b517651f327f5f1e96a3
import pytest

import kind_javascript


def test_ac_kjs_007_runner_sandbox_and_fresh_copy(tmp_path, monkeypatch):
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

    run = kind_javascript.asset_runner(asset)
    assert callable(run)

    # Only PATH reaches the node process, so HOME is not visible.
    assert run("home", []) is None

    # The asset may read no file but its copy and the driver.
    with pytest.raises(kind_javascript.AssetError, match="restricted"):
        run("peek", [str(secret)])

    # The file is copied at call time: a rewrite is seen by the same run.
    asset.write_text(
        "export function home() { return 'new'; }\n",
        encoding="utf-8",
    )
    assert run("home", []) == "new"