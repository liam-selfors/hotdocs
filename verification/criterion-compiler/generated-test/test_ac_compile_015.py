import importlib
import os
import shutil
import sys
from pathlib import Path

import pytest


MODULE_NAME = "criterion_compiler"
SLUG = "criterion-compiler"


def _matching_module_keys():
    return [
        k
        for k in list(sys.modules.keys())
        if k == MODULE_NAME or k.startswith(MODULE_NAME + ".")
    ]


def _real(p):
    return os.path.realpath(str(p))


def _is_under(child, parent):
    child_r = _real(child)
    parent_r = _real(parent)
    try:
        return os.path.commonpath([child_r, parent_r]) == parent_r
    except ValueError:
        return False


def _locate_original_source():
    import criterion_compiler  # noqa: F401

    mod = sys.modules[MODULE_NAME]
    orig_file = getattr(mod, "__file__", None)
    assert orig_file, "criterion_compiler has no __file__; cannot copy its source"
    orig_file = Path(_real(orig_file))
    if orig_file.name == "__init__.py":
        return orig_file.parent, True
    return orig_file, False


def _resolve_criterion_compiler(repo_root):
    """The documented resolution algorithm (R-COMPILE-014)."""
    try:
        import criterion_compiler  # noqa: F401

        return sys.modules[MODULE_NAME]
    except ImportError:
        pass

    candidates = [
        str(Path(repo_root) / "pipeline" / SLUG),
        str(Path(repo_root) / "gen" / SLUG),
    ]
    to_add = [c for c in candidates if c not in sys.path]
    sys.path[0:0] = to_add
    importlib.invalidate_caches()

    import criterion_compiler  # noqa: F401,F811

    return sys.modules[MODULE_NAME]


def test_ac_compile_015_resolves_from_pipeline_location(tmp_path, monkeypatch):
    source, is_package = _locate_original_source()
    source_parent = source.parent

    # Fresh repo_root with the module's own source copied into
    # repo_root/pipeline/criterion-compiler/.
    repo_root = tmp_path / "repo"
    dest_dir = repo_root / "pipeline" / SLUG
    dest_dir.mkdir(parents=True)
    if is_package:
        shutil.copytree(
            str(source),
            str(dest_dir / MODULE_NAME),
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    else:
        shutil.copy2(str(source), str(dest_dir / (MODULE_NAME + ".py")))

    # Snapshot and remove criterion_compiler (and any submodules) from sys.modules.
    saved_modules = {k: sys.modules[k] for k in _matching_module_keys()}
    for k in saved_modules:
        del sys.modules[k]

    # Ensure the plain import fails so the documented fallback is what
    # locates the module: drop the original's parent directory from sys.path.
    new_path = []
    for entry in sys.path:
        entry_dir = entry if entry else os.getcwd()
        try:
            if _real(entry_dir) == _real(source_parent):
                continue
        except Exception:
            pass
        new_path.append(entry)
    monkeypatch.setattr(sys, "path", new_path)
    importlib.invalidate_caches()

    try:
        try:
            import criterion_compiler  # noqa: F401
            plain_import_ok = True
        except ImportError:
            plain_import_ok = False
        finally:
            for k in _matching_module_keys():
                if k not in saved_modules or sys.modules.get(k) is not saved_modules.get(k):
                    sys.modules.pop(k, None)
        if plain_import_ok:
            pytest.fail(
                "criterion_compiler is still importable via a plain import after "
                "removing its source directory from sys.path; cannot arrange for "
                "repo_root/pipeline/criterion-compiler to be the location found"
            )

        module = _resolve_criterion_compiler(repo_root)

        assert module is not None
        mod_file = getattr(module, "__file__", None)
        assert mod_file, "resolved criterion_compiler has no __file__"
        assert _is_under(mod_file, dest_dir), (
            "resolved criterion_compiler.__file__ %r does not lie under %r"
            % (mod_file, str(dest_dir))
        )

        assert hasattr(module, "compile"), "module does not expose compile"
        assert callable(getattr(module, "compile"))
        assert hasattr(module, "compile_criterion"), (
            "module does not expose compile_criterion"
        )
        assert callable(getattr(module, "compile_criterion"))
    finally:
        for k in _matching_module_keys():
            sys.modules.pop(k, None)
        sys.modules.update(saved_modules)
        importlib.invalidate_caches()