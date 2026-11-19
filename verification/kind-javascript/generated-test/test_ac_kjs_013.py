# hotdocs-criterion: sha256:a11da21db579cf10433989e8bf83279ecea6dfce3d8d93c747d3e94b2d416fa6
import ast
import re
from pathlib import Path

import kind_javascript


JS_PATTERN = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")


def _long_javascript_constants(tree):
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if (
                len(text) >= 200
                and JS_PATTERN.search(text) is not None
                and (";" in text or "{" in text)
            ):
                found.append((getattr(node, "lineno", None), text[:80]))
    return found


def test_no_long_javascript_string_constant_in_module():
    source_path = Path(kind_javascript.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders = _long_javascript_constants(tree)

    assert offenders == [], (
        "str constants of 200+ characters holding JavaScript found: "
        + repr(offenders)
    )