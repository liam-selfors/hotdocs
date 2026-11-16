import spec_bundle_assembler

import ast
from pathlib import Path


FORBIDDEN_TOP_LEVEL = {
    "yaml",
    "ruamel",
    "markdown",
    "mistune",
    "frontmatter",
    "commonmark",
}


def _module_source_files():
    module_file = Path(spec_bundle_assembler.__file__).resolve()
    if module_file.name == "__init__.py":
        root = module_file.parent
        files = sorted(
            p for p in root.rglob("*.py")
            if "__pycache__" not in p.parts
        )
    else:
        files = [module_file]
    assert files, "no .py files found for the module under test"
    return files


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top(name):
    return (name or "").split(".")[0]


def _forbidden_imports(tree):
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _top(alias.name) in FORBIDDEN_TOP_LEVEL:
                    hits.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and _top(node.module) in FORBIDDEN_TOP_LEVEL:
                hits.append((node.lineno, node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            is_dynamic_import = (
                (isinstance(func, ast.Name) and func.id == "__import__")
                or (isinstance(func, ast.Attribute) and func.attr == "import_module")
            )
            if is_dynamic_import and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    if _top(first.value) in FORBIDDEN_TOP_LEVEL:
                        hits.append((node.lineno, first.value))
    return hits


def _has_load_corpus_attribute_call(tree):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "load_corpus"
        ):
            return True
    return False


def test_ac_assemble_014_no_reparsing_dependencies_and_uses_load_corpus():
    files = _module_source_files()

    all_hits = {}
    found_load_corpus_call = False
    for path in files:
        tree = _parse(path)
        hits = _forbidden_imports(tree)
        if hits:
            all_hits[str(path)] = hits
        if _has_load_corpus_attribute_call(tree):
            found_load_corpus_call = True

    assert not all_hits, (
        "module under test imports a forbidden YAML/Markdown/frontmatter "
        f"parsing package: {all_hits}"
    )
    assert found_load_corpus_call, (
        "no .py file of the module under test contains a call whose function "
        "is an attribute named load_corpus (e.g. spec_linter.load_corpus(...)); "
        f"files examined: {[str(p) for p in files]}"
    )