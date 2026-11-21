# hotdocs-criterion: sha256:96f162bb1066bf9036e87f51292bca73b156200efd9c81d0a4c27c3a12fb6267
import kind_python


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_ac_kpy_003_flat_module_surface(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    _write(
        tmp_path / "my-mod" / "my_mod.py",
        "import os\nfrom json import dumps\n\nALPHA = 1\n_hidden = 2\n\n\n"
        "def beta():\n    return 3\n\n\nclass Gamma:\n    pass\n",
    )
    result = kind_python.surface(tmp_path / "my-mod")
    assert result == {"names": ["ALPHA", "Gamma", "beta", "dumps", "os"]}


def test_ac_kpy_003_package_surface(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    _write(tmp_path / "pk" / "pk" / "__init__.py", "from .sub import val\n")
    _write(tmp_path / "pk" / "pk" / "sub.py", "val = 1\n")
    result = kind_python.surface(tmp_path / "pk")
    assert result == {"names": ["sub", "val"]}


def test_ac_kpy_003_failing_import_gives_empty_names(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    _write(tmp_path / "bad" / "bad.py", "raise RuntimeError('no')\n")
    result = kind_python.surface(tmp_path / "bad")
    assert result == {"names": []}