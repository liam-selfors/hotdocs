# hotdocs-criterion: sha256:15015c52a0a8f1e4937d54eecda56275f98131ba6dd8cf97d49acf15dc0cba44
import ast
import inspect
from pathlib import Path

import kind_css


FORBIDDEN = {"subprocess", "socket", "http", "urllib", "multiprocessing"}


def _imported_module_names(tree):
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # A relative import names no top-level module of its own.
                continue
            if node.module:
                names.append(node.module)
    return names


def _is_forbidden(name):
    top = name.split(".", 1)[0]
    return top in FORBIDDEN or top.startswith("hotdocs")


def test_ac_kcss_001_names_and_imports():
    assert kind_css.KIND == "css"
    assert kind_css.GATE_VERSION == "kind-css@1.0.0"

    assert inspect.isclass(kind_css.AssetError)
    assert issubclass(kind_css.AssetError, Exception)

    source_path = Path(kind_css.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = _imported_module_names(tree)
    offending = [name for name in imported if _is_forbidden(name)]
    assert offending == [], "forbidden imports: " + repr(offending)


def test_ac_kcss_001_forbidden_check_is_not_vacuous():
    # Sanity check that the examination itself detects each forbidden form.
    sample = (
        "import subprocess\n"
        "import socket as s\n"
        "from http import client\n"
        "import urllib.request\n"
        "from multiprocessing import Pool\n"
        "import hotdocs_core\n"
        "from hotdocs.x import y\n"
        "import os\n"
        "from . import sibling\n"
    )
    names = _imported_module_names(ast.parse(sample))
    flagged = [n for n in names if _is_forbidden(n)]
    assert flagged == [
        "subprocess",
        "socket",
        "http",
        "urllib.request",
        "multiprocessing",
        "hotdocs_core",
        "hotdocs.x",
    ]