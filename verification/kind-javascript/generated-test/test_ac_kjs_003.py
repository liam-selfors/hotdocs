# hotdocs-criterion: sha256:2fccdf8444966ed24e1bba15759acfaef1df27b3c3f890234f230f6cf946b5bc
import shutil
from pathlib import Path

import pytest

import kind_javascript


def test_not_utf8_gives_only_parse_error(tmp_path):
    asset = tmp_path / "notutf8.js"
    asset.write_bytes(b"export const s = '\xff';\n")

    result = kind_javascript.layout_errors(asset)

    assert list(result) == ["parse error: not UTF-8"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_parse_error_then_forbidden_fetch(tmp_path):
    asset = tmp_path / "bad.js"
    asset.write_bytes("export function f(a {\n  return fetch(a);\n}\n".encode("utf-8"))

    result = kind_javascript.layout_errors(asset)

    assert list(result) == [
        "parse error: SyntaxError: Unexpected token '{'",
        "forbidden: fetch(",
    ]