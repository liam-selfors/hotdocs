# hotdocs-criterion: sha256:269dbd3ebaa8d8b26ce6bb3e477a536446b6359d6b929fd2784a6f8cb2c6eeca
import kind_javascript


SOURCE = (
    "export function add(a, b) { return a + b; }\n"
    "export function nothing() {}\n"
    "export async function later(x) { return [x, {k: null}, true]; }\n"
    "export function noisy() { console.log('hi'); return 'ok'; }\n"
)


def test_ac_kjs_005_run_decodes_results(tmp_path):
    path = tmp_path / "m.js"
    path.write_text(SOURCE, encoding="utf-8")

    run = kind_javascript.asset_runner(path)
    assert callable(run)

    result = run("add", [1, 2])
    assert result == 3
    assert not isinstance(result, bool)

    assert run("add", ["a", "b"]) == "ab"

    assert run("nothing", []) is None

    later = run("later", [5])
    assert later == [5, {"k": None}, True]
    assert later[1]["k"] is None
    assert later[2] is True

    assert run("noisy", []) == "ok"