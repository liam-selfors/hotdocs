"""AC-ASSEMBLE-014 (covers R-ASSEMBLE-012).

Given the real, committed spec_bundle_assembler.py source
When its import statements are inspected
Then it imports no standalone YAML- or Markdown-parsing third-party
  package, and its corpus-reading logic calls spec-linter's own
  load_corpus rather than re-parsing any component.md frontmatter
  directly.
"""

import ast
import inspect
import os
from pathlib import Path

import spec_bundle_assembler


FORBIDDEN_TOP_LEVEL_MODULES = {
    # YAML parsers
    "yaml",
    "ruamel",
    "ruamel_yaml",
    "oyaml",
    "strictyaml",
    "yamlcore",
    "pyaml",
    # Frontmatter parsers
    "frontmatter",
    "python_frontmatter",
    # Markdown parsers
    "markdown",
    "markdown2",
    "mistune",
    "commonmark",
    "markdown_it",
    "mistletoe",
    "marko",
    "cmarkgfm",
    "mdit_py_plugins",
}


def _source_files():
    module_file = getattr(spec_bundle_assembler, "__file__", None)
    if not module_file:
        module_file = inspect.getsourcefile(spec_bundle_assembler)
    assert module_file, "could not locate spec_bundle_assembler source file"
    path = Path(module_file)
    if path.suffix != ".py":
        src = inspect.getsourcefile(spec_bundle_assembler)
        assert src, "spec_bundle_assembler has no .py source available"
        path = Path(src)
    assert path.is_file(), f"source file not found: {path}"

    if path.name == "__init__.py":
        files = sorted(
            p for p in path.parent.rglob("*.py") if "__pycache__" not in p.parts
        )
    else:
        files = [path]
    assert files, "no source files found for spec_bundle_assembler"
    return files


def _parsed_sources():
    result = []
    for f in _source_files():
        text = f.read_text(encoding="utf-8")
        result.append((f, ast.parse(text, filename=str(f))))
    return result


def _top(name):
    return (name or "").split(".")[0]


def _call_name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def test_imports_no_standalone_yaml_or_markdown_package():
    offenders = []
    for path, tree in _parsed_sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _top(alias.name) in FORBIDDEN_TOP_LEVEL_MODULES:
                        offenders.append(f"{path}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and _top(node.module) in FORBIDDEN_TOP_LEVEL_MODULES:
                    offenders.append(
                        f"{path}:{node.lineno}: from {node.module} import ..."
                    )
            elif isinstance(node, ast.Call):
                # Dynamic imports: importlib.import_module("yaml"), __import__("yaml")
                name = _call_name(node.func)
                if name in ("import_module", "__import__") and node.args:
                    first = node.args[0]
                    if (
                        isinstance(first, ast.Constant)
                        and isinstance(first.value, str)
                        and _top(first.value) in FORBIDDEN_TOP_LEVEL_MODULES
                    ):
                        offenders.append(
                            f"{path}:{node.lineno}: dynamic import of {first.value!r}"
                        )
    assert not offenders, (
        "spec_bundle_assembler imports a standalone YAML/Markdown parsing "
        "package (R-ASSEMBLE-012):\n" + "\n".join(offenders)
    )


def test_corpus_reading_calls_spec_linter_load_corpus():
    found = []
    for path, tree in _parsed_sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if _call_name(node.func) == "load_corpus":
                    found.append(f"{path}:{node.lineno}")
                # getattr(spec_linter_module, "load_corpus")
                elif _call_name(node.func) == "getattr" and len(node.args) >= 2:
                    attr = node.args[1]
                    if isinstance(attr, ast.Constant) and attr.value == "load_corpus":
                        found.append(f"{path}:{node.lineno}")
    assert found, (
        "spec_bundle_assembler never calls spec-linter's load_corpus; corpus "
        "structure must be read through it (R-ASSEMBLE-012)"
    )


def _is_frontmatter_delimiter(value):
    if not isinstance(value, str):
        return False
    stripped = value.lstrip("^\\A").lstrip("\\n").strip()
    return stripped.startswith("---") and set(stripped[:3]) == {"-"}


FRONTMATTER_SPLIT_CALLS = {
    "split",
    "startswith",
    "partition",
    "rpartition",
    "find",
    "index",
    "removeprefix",
    "match",
    "search",
    "compile",
    "fullmatch",
    "findall",
    "finditer",
    "sub",
}


def test_does_not_reparse_frontmatter_directly():
    offenders = []
    for path, tree in _parsed_sources():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name not in FRONTMATTER_SPLIT_CALLS:
                continue
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(arg, ast.Constant) and _is_frontmatter_delimiter(arg.value):
                    offenders.append(
                        f"{path}:{node.lineno}: {name}({arg.value!r}, ...)"
                    )
    assert not offenders, (
        "spec_bundle_assembler appears to re-parse YAML frontmatter itself "
        "instead of using load_corpus's Corpus/Component objects "
        "(R-ASSEMBLE-012):\n" + "\n".join(offenders)
    )