# hotdocs-criterion: sha256:b74d1f8c813de94661a508aa1127c18cc33e8784be2adf4ed7177423d466b156
import ast
from pathlib import Path

import spec_bundle_assembler


FORBIDDEN_ROOTS = {"yaml", "ruamel", "markdown", "mistune", "frontmatter", "commonmark"}


def _module_files():
    module_file = Path(spec_bundle_assembler.__file__).resolve()
    if module_file.name == "__init__.py":
        root = module_file.parent
        files = sorted(
            p for p in root.rglob("*.py")
            if "__pycache__" not in p.parts
        )
    else:
        files = [module_file]
    return files


def _parse(path):
    source = path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(path))


def _root_name(dotted):
    return dotted.split(".")[0] if dotted else ""


def _forbidden_imports(tree):
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _root_name(alias.name) in FORBIDDEN_ROOTS:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if _root_name(node.module or "") in FORBIDDEN_ROOTS:
                found.append(node.module)
        elif isinstance(node, ast.Call):
            # Dynamic imports by literal name: __import__("yaml"),
            # importlib.import_module("yaml"), import_module("yaml")
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in ("__import__", "import_module") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    if _root_name(first.value) in FORBIDDEN_ROOTS:
                        found.append(first.value)
    return found


def _has_load_corpus_attribute_call(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "load_corpus":
                return True
    return False


def test_module_files_are_found():
    files = _module_files()
    assert files, "no .py files found for spec_bundle_assembler"
    for path in files:
        assert path.is_file()
        assert path.suffix == ".py"


def test_no_forbidden_parser_imports():
    offenders = {}
    for path in _module_files():
        tree = _parse(path)
        bad = _forbidden_imports(tree)
        if bad:
            offenders[str(path)] = bad
    assert offenders == {}, (
        "spec_bundle_assembler must not import a YAML/Markdown/frontmatter "
        "parser; found: " + repr(offenders)
    )


def test_some_file_calls_load_corpus_as_attribute():
    files = _module_files()
    hits = [str(p) for p in files if _has_load_corpus_attribute_call(_parse(p))]
    assert hits, (
        "expected at least one call whose function is an attribute named "
        "load_corpus (e.g. spec_linter.load_corpus(repo_root)) in "
        + repr([str(p) for p in files])
    )