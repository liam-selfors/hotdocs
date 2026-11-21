# hotdocs-criterion: sha256:35e9bf3511c4e92b54564684fca279cc003db679d6dc6f8dcf57199c31c3cad7
import kind_javascript

import pytest

from kind_javascript import AssetError


def test_ac_kjs_007_runner_restricts_env_and_fs_and_copies_at_call_time(tmp_path, monkeypatch):
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

    # Only PATH reaches the process, so HOME is absent.
    assert run("home", []) is None

    # Reading any file other than the copy and the driver is refused.
    with pytest.raises(AssetError, match="restricted"):
        run("peek", [str(secret)])

    # The file is copied at call time: a rewrite is seen by the same run.
    asset.write_text("export function home() { return 'new'; }\n", encoding="utf-8")
    assert run("home", []) == "new"