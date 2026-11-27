# hotdocs-criterion: sha256:c515cac783ab10b4683595d857390ae4a708fdf289f2ac04fe905636d869c273
import kind_python


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_ac_kpy_002_layout_errors_reports_each_unparsable_python_file_in_order(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    d = tmp_path / "lay"
    d.mkdir(parents=True, exist_ok=True)
    _write_text(d / "a.py", "def ok():\n    return 1\n")
    _write_text(d / "b.py", "def f(:\n    pass\n")
    _write_text(d / "b" / "c.py", "x = 1\nif x\n    y = 2\n")
    _write_bytes(d / "n.py", b"x = 1\x00\n")
    _write_bytes(d / "u.py", b"x = '\xff'\n")
    _write_text(d / "__pycache__" / "bad.py", "def (\n")
    _write_text(d / "notes.txt", "def (\n")

    result = kind_python.layout_errors(d)

    assert isinstance(result, list)
    assert len(result) == 4, result
    assert result[0] == "b.py:1: SyntaxError: invalid syntax"
    assert result[1] == "b/c.py:2: SyntaxError: expected ':'"
    assert isinstance(result[2], str)
    assert result[2].startswith("n.py:0: SyntaxError: "), result[2]
    assert isinstance(result[3], str)
    assert result[3].startswith("u.py:1: SyntaxError: "), result[3]

    (d / "b.py").unlink()
    (d / "b" / "c.py").unlink()
    (d / "n.py").unlink()
    (d / "u.py").unlink()

    assert kind_python.layout_errors(d) == []