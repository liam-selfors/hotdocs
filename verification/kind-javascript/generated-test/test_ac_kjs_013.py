# hotdocs-criterion: sha256:60394ee8f60924a62d646424e06bf84ef3f1ecac68a843e8209ffb52185e807b
import ast
import re
from pathlib import Path

import kind_javascript


JS_PATTERN = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")


def _module_source():
    path = Path(kind_javascript.__file__)
    return path.read_text(encoding="utf-8")


def test_public_interface_present():
    assert callable(kind_javascript.asset_runner)


def test_no_long_javascript_string_constant_in_module():
    source = _module_source()
    tree = ast.parse(source)

    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if (
                len(text) >= 200
                and JS_PATTERN.search(text) is not None
                and (";" in text or "{" in text)
            ):
                offenders.append(
                    (getattr(node, "lineno", None), len(text), text[:80])
                )

    assert offenders == [], (
        "str constants holding JavaScript that are 200 characters or longer: "
        + repr(offenders)
    )