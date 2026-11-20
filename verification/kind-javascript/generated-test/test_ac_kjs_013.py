# hotdocs-criterion: sha256:3c2c2f6c2eb02209ed7ded7428fca82537c9d3af5025aeb542975127e77b1ce8
import ast
import re
from pathlib import Path

import kind_javascript


JS_PATTERN = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")


def _string_constants(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node


def test_ac_kjs_013_no_long_javascript_string_constants():
    source_path = Path(kind_javascript.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders = []
    for node in _string_constants(tree):
        value = node.value
        if (
            JS_PATTERN.search(value)
            and (";" in value or "{" in value)
            and len(value) >= 200
        ):
            offenders.append(
                (getattr(node, "lineno", None), len(value), value[:80])
            )

    assert offenders == [], (
        "string constants holding JavaScript of 200 characters or longer: "
        + repr(offenders)
    )