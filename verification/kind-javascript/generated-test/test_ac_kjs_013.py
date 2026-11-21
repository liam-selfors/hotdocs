# hotdocs-criterion: sha256:ac4b2a337d6fbbb29bfbbc00883c2122605a300367e30db66d3457ed30a477b8
import ast
import re
from pathlib import Path

import kind_javascript


JS_PATTERN = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")


def _str_constants(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node


def test_no_long_javascript_string_constant_in_module():
    source_path = Path(kind_javascript.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders = []
    for node in _str_constants(tree):
        value = node.value
        if (
            JS_PATTERN.search(value)
            and (";" in value or "{" in value)
            and len(value) >= 200
        ):
            offenders.append((getattr(node, "lineno", None), len(value), value[:80]))

    assert offenders == [], (
        "string constants holding JavaScript of 200 characters or longer: "
        + repr(offenders)
    )