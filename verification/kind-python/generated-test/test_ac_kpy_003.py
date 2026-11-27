# hotdocs-criterion: sha256:7d5fb995f7172c755121f1b1c8822b527a2199f4b6e1db7da0fee15b0734aec8
import kind_python


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_surface_flat_module_public_names(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    code_dir = tmp_path / "my-mod"
    _write(
        code_dir / "my_mod.py",
        "import os\nfrom json import dumps\n\nALPHA = 1\n_hidden = 2\n\n\n"
        "def beta():\n    return 3\n\n\nclass Gamma:\n    pass\n",
    )
    result = kind_python.surface(code_dir)
    assert result == {"names": ["ALPHA", "Gamma", "beta", "dumps", "os"]}


def test_surface_package_public_names(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    code_dir = tmp_path / "pk"
    _write(code_dir / "pk" / "__init__.py", "from .sub import val\n")
    _write(code_dir / "pk" / "sub.py", "val = 1\n")
    result = kind_python.surface(code_dir)
    assert result == {"names": ["sub", "val"]}


def test_surface_import_failure_gives_empty_names(tmp_path, monkeypatch):
    monkeypatch.delenv("HOTDOCS_PYTHON", raising=False)
    code_dir = tmp_path / "bad"
    _write(code_dir / "bad.py", "raise RuntimeError('no')\n")
    result = kind_python.surface(code_dir)
    assert result == {"names": []}