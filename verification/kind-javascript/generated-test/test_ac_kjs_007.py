# hotdocs-criterion: sha256:f2e1143b06348f516cae1d532765daf0914eeed8bd7b24932315ef1ca8e52f96
import pytest

import kind_javascript


M_JS = (
    "import { readFileSync } from 'node:fs';\n"
    "export function home() { return process.env.HOME ?? null; }\n"
    "export function peek(p) { return readFileSync(p, 'utf8'); }\n"
)


def test_ac_kjs_007(tmp_path, monkeypatch):
    secret = tmp_path / "secret.txt"
    secret.write_text("s3cret", encoding="utf-8")
    m = tmp_path / "m.js"
    m.write_text(M_JS, encoding="utf-8")
    monkeypatch.setenv("HOME", "/home/x")

    run = kind_javascript.asset_runner(m)
    assert callable(run)

    # Only PATH reaches the process.
    assert run("home", []) is None

    # The asset may read no file other than its copy and the driver.
    with pytest.raises(kind_javascript.AssetError, match="restricted"):
        run("peek", [str(secret)])

    # The file is copied at call time.
    m.write_text("export function home() { return 'new'; }\n", encoding="utf-8")
    assert run("home", []) == "new"