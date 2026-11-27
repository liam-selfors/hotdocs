"""Provision the asset kinds and test drivers a component's tests need."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PLUGIN_NAME = "hotdocs_run_plugins"

PLUGIN_SOURCE = '''"""Pytest plugin written by run-environment: asset_runner and driver fixtures."""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


def _load(adapter):
    name = Path(adapter).stem
    spec = importlib.util.spec_from_file_location(name, adapter)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def asset_runner():
    entries = json.loads(os.environ.get("HOTDOCS_ASSETS", "[]"))

    def run(path):
        for entry in entries:
            if entry["path"] == path:
                module = _load(entry["adapter"])
                return module.asset_runner(Path(entry["file"]))
        declared = ", ".join(entry["path"] for entry in entries) or "none"
        raise KeyError(
            "asset_runner: %r is not a declared asset (declared: %s)" % (path, declared)
        )

    return run


def _driver_fixture(entry):
    @pytest.fixture(name=entry["fixture"])
    def driver_fixture(tmp_path):
        module = _load(entry["adapter"])
        session = module.open_session(Path(entry["repo_root"]), tmp_path)
        try:
            yield session
        finally:
            session.close()

    return driver_fixture


for _index, _entry in enumerate(json.loads(os.environ.get("HOTDOCS_DRIVERS", "[]"))):
    globals()["_hotdocs_driver_fixture_%d" % _index] = _driver_fixture(_entry)
'''


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).absolute().parents if p.name == "gen")


def _sha256(path: Path):
    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _frontmatter_lines(path: Path) -> list:
    if not path.is_file():
        return []
    front = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if line.strip() == "---":
            break
        front.append(line)
    return front


def _list_items(lines: list, key: str) -> list:
    for line in lines:
        if line.startswith(key + ":"):
            inner = line[line.index("[") + 1 : line.index("]")]
            return [item.strip() for item in inner.split(",") if item.strip()]
    return []


def _find_adapter(repo_root: Path, prefix: str, name: str):
    rel = Path("gen", f"{prefix}-{name}", f"{prefix}_{name.replace('-', '_')}.py")
    for root in (Path(repo_root), _tool_root()):
        candidate = root / rel
        if candidate.is_file():
            return Path(os.path.abspath(candidate))
    return None


def _load_module(path: Path):
    name = path.stem
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _provision(names, label, repo_root, adapters, reports, modules):
    for name in names:
        path = adapters[name]
        if path is None:
            return f"unknown {label}: {name}"
        try:
            module = _load_module(path)
            report = module.provision(Path(repo_root))
        except Exception as exc:
            return f"{name} adapter failed: {type(exc).__name__}: {exc}"
        reports[name] = report
        modules[name] = module
        if not _get(report, "ok"):
            return _get(report, "reason")
    return None


def _reported(report):
    if report is None:
        return {}, None
    return _get(report, "versions"), _get(report, "lockfile_sha256")


def _hash_or_none(path):
    if path is None:
        return None
    return _sha256(path)


@dataclass
class RunEnvironment:
    ok: bool
    failure_message: str | None
    interpreter: str | None
    assets: list
    drivers: list
    plugin_dir: str | None
    _asset_entries: list = field(default_factory=list, repr=False)
    _driver_entries: list = field(default_factory=list, repr=False)

    def pytest_args(self) -> list:
        return ["-p", PLUGIN_NAME]

    def driver_fixtures(self) -> list:
        return [entry["fixture"] for entry in self._driver_entries]

    def env_for(self, code_dir: Path) -> dict:
        assets = [
            {
                "path": entry["path"],
                "file": str(Path(code_dir) / entry["path"]),
                "adapter": entry["adapter"],
            }
            for entry in self._asset_entries
        ]
        return {
            "HOTDOCS_ASSETS": json.dumps(assets),
            "HOTDOCS_DRIVERS": json.dumps(self._driver_entries),
        }

    def close(self) -> None:
        if self.plugin_dir is not None:
            shutil.rmtree(self.plugin_dir, ignore_errors=True)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "failure_message": self.failure_message,
            "interpreter": self.interpreter,
            "assets": [dict(entry) for entry in self.assets],
            "drivers": [dict(entry) for entry in self.drivers],
            "plugin_dir": self.plugin_dir,
        }


def _build(repo_root: Path, declared_assets: list, declared_drivers: list) -> RunEnvironment:
    repo_root = Path(repo_root)
    arch = repo_root / "specs" / "architecture"
    kinds = list(dict.fromkeys(["python"] + [kind for kind, _ in declared_assets]))
    drivers = sorted(set(declared_drivers))

    kind_adapters = {kind: _find_adapter(repo_root, "kind", kind) for kind in kinds}
    driver_adapters = {name: _find_adapter(repo_root, "driver", name) for name in drivers}

    kind_reports: dict = {}
    kind_modules: dict = {}
    driver_reports: dict = {}
    driver_modules: dict = {}

    failure = _provision(kinds, "asset kind", repo_root, kind_adapters, kind_reports, kind_modules)
    if failure is None:
        failure = _provision(
            drivers, "test driver", repo_root, driver_adapters, driver_reports, driver_modules
        )

    assets = []
    for kind, path in [("python", ".")] + list(declared_assets):
        versions, lockfile = _reported(kind_reports.get(kind))
        assets.append(
            {
                "kind": kind,
                "path": path,
                "definition_sha256": _sha256(arch / f"asset-kind-{kind}.md"),
                "adapter_sha256": _hash_or_none(kind_adapters[kind]),
                "versions": versions,
                "lockfile_sha256": lockfile,
            }
        )

    driver_entries = []
    for name in drivers:
        versions, lockfile = _reported(driver_reports.get(name))
        driver_entries.append(
            {
                "name": name,
                "definition_sha256": _sha256(arch / f"test-driver-{name}.md"),
                "adapter_sha256": _hash_or_none(driver_adapters[name]),
                "versions": versions,
                "lockfile_sha256": lockfile,
            }
        )

    if failure is not None:
        return RunEnvironment(
            ok=False,
            failure_message=failure,
            interpreter=None,
            assets=assets,
            drivers=driver_entries,
            plugin_dir=None,
        )

    plugin_dir = tempfile.mkdtemp()
    (Path(plugin_dir) / f"{PLUGIN_NAME}.py").write_text(PLUGIN_SOURCE, encoding="utf-8")

    absolute_root = os.path.abspath(repo_root)
    return RunEnvironment(
        ok=True,
        failure_message=None,
        interpreter=_get(kind_reports["python"], "interpreter"),
        assets=assets,
        drivers=driver_entries,
        plugin_dir=plugin_dir,
        _asset_entries=[
            {"path": path, "adapter": str(kind_adapters[kind])}
            for kind, path in declared_assets
        ],
        _driver_entries=[
            {
                "name": name,
                "fixture": getattr(driver_modules[name], "FIXTURE"),
                "adapter": str(driver_adapters[name]),
                "repo_root": absolute_root,
            }
            for name in drivers
        ],
    )


def prepare(component_id: str, repo_root: Path) -> RunEnvironment:
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    lines = _frontmatter_lines(Path(repo_root) / "specs" / "components" / slug / "component.md")
    declared_assets = []
    for item in _list_items(lines, "assets"):
        kind, _, path = item.partition(":")
        declared_assets.append((kind.strip(), path.strip()))
    return _build(repo_root, declared_assets, _list_items(lines, "drivers"))


def prepare_capability(capability_id: str, repo_root: Path) -> RunEnvironment:
    drivers: list = []
    for spec_file in sorted((Path(repo_root) / "specs" / "product").glob("*.md")):
        lines = _frontmatter_lines(spec_file)
        ids = [line[len("id:"):].strip() for line in lines if line.startswith("id:")]
        if capability_id in ids:
            drivers = _list_items(lines, "drivers")
            break
    return _build(repo_root, [], drivers)
