# hotdocs-criterion: sha256:183210447dd7eb3b9dd27bf097b0fa3fc8af9c9c3c9fae2c8cdd361d72f42274
import kind_javascript


def test_ac_kjs_005_run_decodes_json_results(tmp_path):
    asset = tmp_path / "m.js"
    asset.write_text(
        "export function add(a, b) { return a + b; }\n"
        "export function nothing() {}\n"
        "export async function later(x) { return [x, {k: null}, true]; }\n"
        "export function noisy() { console.log('hi'); return 'ok'; }\n",
        encoding="utf-8",
    )

    run = kind_javascript.asset_runner(asset)
    assert callable(run)

    result = run("add", [1, 2])
    assert result == 3
    assert not isinstance(result, bool)

    assert run("add", ["a", "b"]) == "ab"

    assert run("nothing", []) is None

    later = run("later", [5])
    assert later == [5, {"k": None}, True]
    assert later[2] is True
    assert later[1]["k"] is None

    assert run("noisy", []) == "ok"