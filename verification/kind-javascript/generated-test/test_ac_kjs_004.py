# hotdocs-criterion: sha256:22dd471adb53453be503a3ab327556fce60aff6ecc776dfddce97f8735a0a4b9
import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_kjs_004_surface_lists_sorted_export_names(tmp_path):
    js = tmp_path / "m.js"
    js.write_text(
        "export function beta(x) { return x; }\n"
        "export const alpha = 1;\n"
        "function hidden() { return 2; }\n"
        "export default 3;\n",
        encoding="utf-8",
    )
    result = kind_javascript.surface(js)
    assert result == {"names": ["alpha", "beta", "default"]}
    assert field(result, "names") == ["alpha", "beta", "default"]


def test_ac_kjs_004_surface_of_unparseable_file_is_empty(tmp_path):
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    js = bad_dir / "m.js"
    js.write_text("export function f( {\n", encoding="utf-8")
    result = kind_javascript.surface(js)
    assert result == {"names": []}