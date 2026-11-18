# hotdocs-criterion: sha256:b74d1f8c813de94661a508aa1127c18cc33e8784be2adf4ed7177423d466b156
import ast
from pathlib import Path

import spec_bundle_assembler


FORBIDDEN_TOP_LEVEL = {
    "yaml",
    "ruamel",
    "markdown",
    "mistune",
    "frontmatter",
    "commonmark",
}


def _module_py_files():
    module_file = Path(spec_bundle_assembler.__file__).resolve()
    if module_file.name == "__init__.py":
        package_dir = module_file.parent
        files = sorted(
            p
            for p in package_dir.rglob("*.py")
            if "__pycache__" not in p.parts
        )
    else:
        files = [module_file]
    return files


def _top_level(name):
    if not name:
        return ""
    return name.split(".", 1)[0]


def _forbidden_imports_in_tree(tree):
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = _top_level(alias.name)
                if top in FORBIDDEN_TOP_LEVEL:
                    hits.append((getattr(node, "lineno", None), alias.name))
        elif isinstance(node, ast.ImportFrom):
            if (node.level or 0) == 0:
                top = _top_level(node.module)
                if top in FORBIDDEN_TOP_LEVEL:
                    hits.append((getattr(node, "lineno", None), node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            func_name = None
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name in ("__import__", "import_module") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    top = _top_level(first.value)
                    if top in FORBIDDEN_TOP_LEVEL:
                        hits.append((getattr(node, "lineno", None), first.value))
    return hits


def _has_load_corpus_attribute_call(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "load_corpus":
                return True
    return False


def test_ac_assemble_014_no_third_party_parsers_and_uses_load_corpus():
    files = _module_py_files()
    assert files, "no .py files found for spec_bundle_assembler"

    forbidden = {}
    any_load_corpus_call = False

    for path in files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        hits = _forbidden_imports_in_tree(tree)
        if hits:
            forbidden[str(path)] = hits
        if _has_load_corpus_attribute_call(tree):
            any_load_corpus_call = True

    assert not forbidden, (
        "spec_bundle_assembler imports a forbidden YAML/Markdown/frontmatter "
        "parser (R-ASSEMBLE-012): %r" % (forbidden,)
    )
    assert any_load_corpus_call, (
        "no .py file of spec_bundle_assembler contains a call whose function "
        "is an attribute named load_corpus (R-ASSEMBLE-012); files scanned: %r"
        % ([str(p) for p in files],)
    )