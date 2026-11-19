# hotdocs-criterion: sha256:5864f290f7f93437ad63f4adda738bb8c9289d176e5ee5df34718412dee2da99
import kind_javascript


SOURCE = (
    "export function add(a, b) { return a + b; }\n"
    "export function nothing() {}\n"
    "export async function later(x) { return [x, {k: null}, true]; }\n"
    "export function noisy() { console.log('hi'); return 'ok'; }\n"
)


def test_ac_kjs_005_run_decodes_json_results(tmp_path):
    asset = tmp_path / "m.js"
    asset.write_text(SOURCE, encoding="utf-8")

    run = kind_javascript.asset_runner(asset)
    assert callable(run)

    result = run("add", [1, 2])
    assert result == 3
    assert isinstance(result, int) and not isinstance(result, bool)

    result = run("add", ["a", "b"])
    assert result == "ab"
    assert isinstance(result, str)

    assert run("nothing", []) is None

    result = run("later", [5])
    assert result == [5, {"k": None}, True]
    assert isinstance(result, list)
    assert result[2] is True
    assert result[1]["k"] is None

    result = run("noisy", [])
    assert result == "ok"