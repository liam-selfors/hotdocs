# hotdocs-criterion: sha256:8c63e02325de8029f2f2b23d869af8c86937e446f729f747a7de85a9f75b7f10
import ast
from pathlib import Path

import spec_bundle_assembler


FORBIDDEN = {"yaml", "ruamel", "markdown", "mistune", "frontmatter", "commonmark"}


def _module_files():
    module_file = Path(spec_bundle_assembler.__file__).resolve()
    if module_file.name == "__init__.py":
        files = sorted(p for p in module_file.parent.rglob("*.py") if p.is_file())
    else:
        files = [module_file]
    assert files, "no .py files found for spec_bundle_assembler"
    return files


def _parse(path):
    source = path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(path))


def _imported_top_names(tree):
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append((alias.name.split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.append((node.module.split(".")[0], node.lineno))
    return names


def _has_load_corpus_attribute_call(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "load_corpus":
                return True
    return False


def test_no_forbidden_parser_imports_and_load_corpus_attribute_call():
    files = _module_files()
    trees = {path: _parse(path) for path in files}

    offenders = []
    for path, tree in trees.items():
        for name, lineno in _imported_top_names(tree):
            if name in FORBIDDEN:
                offenders.append(str(path) + ":" + str(lineno) + " imports " + name)
    assert not offenders, "forbidden third-party parser imports found: " + repr(offenders)

    assert any(_has_load_corpus_attribute_call(tree) for tree in trees.values()), (
        "no call whose function is an attribute named load_corpus found in "
        + repr([str(p) for p in files])
    )