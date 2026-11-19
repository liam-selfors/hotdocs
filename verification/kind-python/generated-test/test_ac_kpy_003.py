# hotdocs-criterion: sha256:670482c6e5c915f7d9ca14d3d02d798e18cd888a92a880e420e9512d1ed81a0d
import sys

import kind_python


def _use_running_interpreter(monkeypatch):
    monkeypatch.setenv("HOTDOCS_PYTHON", sys.executable)


def _names_result(value):
    return value


def test_surface_flat_module_lists_sorted_public_names(tmp_path, monkeypatch):
    _use_running_interpreter(monkeypatch)
    code_dir = tmp_path / "my-mod"
    code_dir.mkdir()
    (code_dir / "my_mod.py").write_text(
        "import os\nfrom json import dumps\n\nALPHA = 1\n_hidden = 2\n\n\n"
        "def beta():\n    return 3\n\n\nclass Gamma:\n    pass\n"
    )

    result = kind_python.surface(code_dir)

    assert result == {"names": ["ALPHA", "Gamma", "beta", "dumps", "os"]}


def test_surface_package_lists_submodule_and_imported_name(tmp_path, monkeypatch):
    _use_running_interpreter(monkeypatch)
    code_dir = tmp_path / "pk"
    pkg = code_dir / "pk"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("from .sub import val\n")
    (pkg / "sub.py").write_text("val = 1\n")

    result = kind_python.surface(code_dir)

    assert result == {"names": ["sub", "val"]}


def test_surface_module_raising_on_import_gives_empty_names(tmp_path, monkeypatch):
    _use_running_interpreter(monkeypatch)
    code_dir = tmp_path / "bad"
    code_dir.mkdir()
    (code_dir / "bad.py").write_text("raise RuntimeError('no')\n")

    result = kind_python.surface(code_dir)

    assert result == {"names": []}