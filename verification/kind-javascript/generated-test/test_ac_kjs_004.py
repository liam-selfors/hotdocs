# hotdocs-criterion: sha256:1046a15f5f9699eddd3de4ac6573fa2310d6cccc95102f764ab5ceace23057bc
import kind_javascript


def test_ac_kjs_004_surface_lists_sorted_export_names(tmp_path):
    asset = tmp_path / "m.js"
    asset.write_text(
        "export function beta(x) { return x; }\n"
        "export const alpha = 1;\n"
        "function hidden() { return 2; }\n"
        "export default 3;\n",
        encoding="utf-8",
    )
    result = kind_javascript.surface(asset)
    assert result == {"names": ["alpha", "beta", "default"]}


def test_ac_kjs_004_surface_of_unparseable_file_is_empty(tmp_path):
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    asset = bad_dir / "m.js"
    asset.write_text("export function f( {\n", encoding="utf-8")
    result = kind_javascript.surface(asset)
    assert result == {"names": []}