# hotdocs-criterion: sha256:08d3cc23d17c60e2b8f3ea85f44d170f2c4856105f2d61dab5a22e1dabdb2491
import importlib
import importlib.abc
import shutil
import sys
from pathlib import Path

import criterion_compiler


MODULE_NAME = "criterion_compiler"


def _source_of_module():
    """Return (path, is_package) for the real module under test."""
    origin = Path(criterion_compiler.__file__).resolve()
    if origin.name == "__init__.py":
        return origin.parent, True
    return origin, False


def _provides_module(entry):
    base = Path(entry) if entry else Path.cwd()
    try:
        return (base / (MODULE_NAME + ".py")).is_file() or (
            base / MODULE_NAME / "__init__.py"
        ).is_file()
    except OSError:
        return False


class _BlockPlainImport(importlib.abc.MetaPathFinder):
    """Make the first (plain) import attempt fail, as when the module is not
    otherwise importable, so the documented fallback paths get used."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == MODULE_NAME or fullname.startswith(MODULE_NAME + "."):
            raise ImportError("blocked plain import of " + fullname)
        return None


def _resolve(repo_root, blocker):
    """The documented resolution algorithm (R-COMPILE-014)."""
    try:
        sys.meta_path.insert(0, blocker)
        try:
            return importlib.import_module(MODULE_NAME)
        finally:
            sys.meta_path.remove(blocker)
    except ImportError:
        pass
    candidates = [
        repo_root / "pipeline" / "criterion-compiler",
        repo_root / "gen" / "criterion-compiler",
    ]
    for candidate in reversed(candidates):
        sys.path.insert(0, str(candidate))
    importlib.invalidate_caches()
    return importlib.import_module(MODULE_NAME)


def test_resolves_from_pipeline_criterion_compiler(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    location = repo_root / "pipeline" / "criterion-compiler"
    location.mkdir(parents=True)

    source, is_package = _source_of_module()
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    if is_package:
        shutil.copytree(source, location / MODULE_NAME, ignore=ignore)
    else:
        shutil.copy2(source, location / (MODULE_NAME + ".py"))

    # Fresh state: module (and any submodules) removed from sys.modules;
    # monkeypatch restores the originals at teardown.
    for key in list(sys.modules):
        if key == MODULE_NAME or key.startswith(MODULE_NAME + "."):
            monkeypatch.delitem(sys.modules, key)

    # Drop sys.path entries that would otherwise provide the original module.
    filtered = [p for p in sys.path if not _provides_module(p)]
    monkeypatch.setattr(sys, "path", filtered)
    monkeypatch.setattr(sys, "meta_path", list(sys.meta_path))
    importlib.invalidate_caches()

    module = _resolve(repo_root, _BlockPlainImport())

    module_file = Path(module.__file__).resolve()
    location_resolved = location.resolve()
    assert module_file == location_resolved or location_resolved in module_file.parents, (
        "module resolved from " + str(module_file) + ", expected under " + str(location_resolved)
    )
    assert hasattr(module, "compile") and callable(module.compile)
    assert hasattr(module, "compile_criterion") and callable(module.compile_criterion)