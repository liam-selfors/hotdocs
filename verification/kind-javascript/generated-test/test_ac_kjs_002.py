# hotdocs-criterion: sha256:41dd38ffd29ef1a82706f5a615949b844e0936b045ec1811cd0131479125c4c4
import shutil
from pathlib import Path

import pytest

import kind_javascript


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


@pytest.fixture
def need_node():
    if shutil.which("node") is None:
        pytest.skip("node is not on PATH; the parse check needs it")


def test_ac_kjs_002_forbidden_words_only_outside_strings_and_comments(tmp_path, need_node):
    clean_text = (
        "// import x from 'y'; fetch(\n"
        "const s = \"require('fs') and new WebSocket(u)\";\n"
        "export function f(a) { return a + 1; }\n"
    )
    clean = _write(tmp_path / "app.js", clean_text)

    result = kind_javascript.layout_errors(Path(clean))
    assert list(result) == []

    dirty_text = (
        "import x from './x.js';\n"
        "export function g(u) { fetch(u); require (u); return new XMLHttpRequest(); }\n"
        "export const h = () => import('./y.js') && new WebSocket('ws://a');\n"
    )
    dirty = _write(tmp_path / "other" / "app.js", dirty_text)

    result = kind_javascript.layout_errors(Path(dirty))
    assert list(result) == [
        "forbidden: import",
        "forbidden: fetch(",
        "forbidden: require(",
        "forbidden: XMLHttpRequest",
        "forbidden: import",
        "forbidden: WebSocket",
    ]