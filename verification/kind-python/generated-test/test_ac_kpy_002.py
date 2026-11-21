# hotdocs-criterion: sha256:763a513f4c14800175f6e185376cd1acb7a491cbe8a60d2504df27bf817a5c60
import kind_python


def _write(d, rel, content):
    path = d / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def test_ac_kpy_002_layout_errors_reports_unparsable_python_files(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)

    d = tmp_path / "lay"
    d.mkdir()
    _write(d, "a.py", "def ok():\n    return 1\n")
    _write(d, "b.py", "def f(:\n    pass\n")
    _write(d, "b/c.py", "x = 1\nif x\n    y = 2\n")
    _write(d, "n.py", b"x = 1\x00\n")
    _write(d, "u.py", b"x = '\xff'\n")
    _write(d, "__pycache__/bad.py", "def (\n")
    _write(d, "notes.txt", "def (\n")

    result = kind_python.layout_errors(d)

    assert isinstance(result, list)
    assert len(result) == 4, result
    assert result[0] == "b.py:1: SyntaxError: invalid syntax"
    assert result[1] == "b/c.py:2: SyntaxError: expected ':'"
    assert isinstance(result[2], str)
    assert result[2].startswith("n.py:0: SyntaxError: "), result[2]
    assert isinstance(result[3], str)
    assert result[3].startswith("u.py:1: SyntaxError: "), result[3]

    for rel in ("b.py", "b/c.py", "n.py", "u.py"):
        (d / rel).unlink()

    assert kind_python.layout_errors(d) == []