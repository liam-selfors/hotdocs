# hotdocs-criterion: sha256:c20a249cc890304dbeddaa0f0de1b50e814f848b1f6ea42a33c9a5da2ca3e85f
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


def _top(name):
    return name.split(".")[0] if name else ""


def _forbidden_imports(tree):
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _top(alias.name) in FORBIDDEN:
                    found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if (node.level or 0) == 0 and node.module and _top(node.module) in FORBIDDEN:
                found.append((node.lineno, node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            fname = None
            if isinstance(func, ast.Name):
                fname = func.id
            elif isinstance(func, ast.Attribute):
                fname = func.attr
            if fname in ("import_module", "__import__") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    if _top(first.value) in FORBIDDEN:
                        found.append((node.lineno, first.value))
    return found


def _has_load_corpus_attribute_call(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "load_corpus":
                return True
    return False


def test_no_forbidden_parser_imports_and_load_corpus_is_called():
    files = _module_files()
    offenders = []
    any_load_corpus = False
    for path in files:
        tree = _parse(path)
        for lineno, name in _forbidden_imports(tree):
            offenders.append(str(path) + ":" + str(lineno) + " imports " + name)
        if _has_load_corpus_attribute_call(tree):
            any_load_corpus = True

    assert offenders == [], "forbidden third-party parser imports found: " + repr(offenders)
    assert any_load_corpus, (
        "no call whose function is an attribute named load_corpus found in "
        + repr([str(p) for p in files])
    )