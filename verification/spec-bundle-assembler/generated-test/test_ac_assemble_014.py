# hotdocs-criterion: sha256:3434c00264948afdcd495f6950feee36d43019e6e8f3b2092482c2c175d42046
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
    return (name or "").split(".")[0]


def _forbidden_imports(tree):
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _top(alias.name) in FORBIDDEN:
                    found.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and _top(node.module) in FORBIDDEN:
                found.append((node.lineno, node.module))
    return found


def _calls_load_corpus_attribute(tree):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "load_corpus"
        ):
            return True
    return False


def test_no_forbidden_parser_imports_and_load_corpus_called_via_attribute():
    files = _module_files()
    offenders = {}
    any_load_corpus_call = False
    for path in files:
        tree = _parse(path)
        bad = _forbidden_imports(tree)
        if bad:
            offenders[str(path)] = bad
        if _calls_load_corpus_attribute(tree):
            any_load_corpus_call = True

    assert offenders == {}, (
        "module under test imports a forbidden third-party parser: "
        + repr(offenders)
    )
    assert any_load_corpus_call, (
        "no .py file of spec_bundle_assembler contains a call whose function "
        "is an attribute named load_corpus"
    )