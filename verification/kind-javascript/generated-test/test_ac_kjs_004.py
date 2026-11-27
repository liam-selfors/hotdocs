# hotdocs-criterion: sha256:4aeff9e508739fd43f4e074f39dbe767fe89a317d8ed66a3aee1bcbde8ab4647
import kind_javascript


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_surface_lists_sorted_export_names(tmp_path):
    path = tmp_path / "m.js"
    path.write_text(
        "export function beta(x) { return x; }\n"
        "export const alpha = 1;\n"
        "function hidden() { return 2; }\n"
        "export default 3;\n",
        encoding="utf-8",
    )
    result = kind_javascript.surface(path)
    assert result == {"names": ["alpha", "beta", "default"]}
    assert field(result, "names") == ["alpha", "beta", "default"]


def test_surface_of_unparseable_file_is_empty(tmp_path):
    path = tmp_path / "bad.js"
    path.write_text("export function f( {\n", encoding="utf-8")
    result = kind_javascript.surface(path)
    assert result == {"names": []}