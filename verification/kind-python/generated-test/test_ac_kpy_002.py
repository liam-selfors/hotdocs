# hotdocs-criterion: sha256:adceab6a1fa09d20d060e3ed0c6caaafe376cad38233a604dfebb8c9ba39ba3d
from pathlib import Path

import kind_python


def _build(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "b").mkdir(parents=True, exist_ok=True)
    (d / "__pycache__").mkdir(parents=True, exist_ok=True)
    (d / "a.py").write_text("def ok():\n    return 1\n")
    (d / "b.py").write_text("def f(:\n    pass\n")
    (d / "b" / "c.py").write_text("x = 1\nif x\n    y = 2\n")
    (d / "n.py").write_bytes(b"x = 1\x00\n")
    (d / "u.py").write_bytes(b"x = '\xff'\n")
    (d / "__pycache__" / "bad.py").write_text("def (\n")
    (d / "notes.txt").write_text("def (\n")


def test_ac_kpy_002_layout_errors_order_and_messages(tmp_path):
    d = tmp_path / "lay"
    _build(d)

    result = kind_python.layout_errors(d)

    assert isinstance(result, list)
    assert len(result) == 4, result
    assert result[0] == "b.py:1: SyntaxError: invalid syntax"
    assert result[1] == "b/c.py:2: SyntaxError: expected ':'"
    assert result[2].startswith("n.py:0: SyntaxError: "), result[2]
    assert result[3].startswith("u.py:1: SyntaxError: "), result[3]

    for name in ["b.py", "b/c.py", "n.py", "u.py"]:
        (d / name).unlink()

    assert kind_python.layout_errors(d) == []