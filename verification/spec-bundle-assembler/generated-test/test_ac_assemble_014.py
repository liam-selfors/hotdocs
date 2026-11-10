import ast
from pathlib import Path

import spec_bundle_assembler


FORBIDDEN_IMPORTS = {"yaml", "ruamel", "markdown", "mistune", "frontmatter", "commonmark"}


def _module_py_files():
    module_file = Path(spec_bundle_assembler.__file__).resolve()
    if module_file.name == "__init__.py":
        package_dir = module_file.parent
        return sorted(package_dir.rglob("*.py"))
    return [module_file]


def _imported_top_level_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _has_load_corpus_attribute_call(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "load_corpus":
                return True
    return False


def test_module_files_avoid_markup_deps_and_call_load_corpus_via_attribute():
    py_files = _module_py_files()
    assert py_files, "expected at least one .py file for the module under test"

    found_load_corpus_call = False

    for py_file in py_files:
        source = py_file.read_text()
        tree = ast.parse(source, filename=str(py_file))

        imported = _imported_top_level_names(tree)
        forbidden_hit = imported & FORBIDDEN_IMPORTS
        assert not forbidden_hit, (
            f"{py_file} imports forbidden third-party module(s): {forbidden_hit}"
        )

        if _has_load_corpus_attribute_call(tree):
            found_load_corpus_call = True

    assert found_load_corpus_call, (
        "expected at least one call of the form <something>.load_corpus(...) "
        "across the module under test's .py files"
    )