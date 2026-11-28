"""Provisions asset kinds and test drivers for a component's or capability's tests."""

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PLUGIN_NAME = "hotdocs_run_plugins"

PLUGIN_SOURCE = '''"""pytest plugin giving every run asset_runner and each declared driver's fixture."""

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest


def _load(adapter):
    name = "hotdocs_adapter_" + Path(adapter).stem
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
                return _load(entry["adapter"]).asset_runner(Path(entry["file"]))
        declared = ", ".join(entry["path"] for entry in entries) or "none"
        raise KeyError(
            "asset_runner: " + repr(path)
            + " is not a declared asset (declared: " + declared + ")"
        )

    return run


def _copy_screenshots(request, tmp_path):
    root = os.environ.get("HOTDOCS_SCREENSHOTS")
    if not root:
        return
    try:
        stem = Path(str(request.path)).stem
        target = Path(root) / stem
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        pngs = sorted((tmp_path / "screenshots").glob("*.png"))
    except Exception:
        return
    for png in pngs:
        try:
            shutil.copy2(png, target / png.name)
        except Exception:
            pass


def _make_driver_fixture(entry):
    def driver_fixture(request, tmp_path):
        module = _load(entry["adapter"])
        session = module.open_session(Path(entry["repo_root"]), tmp_path)
        try:
            yield session
        finally:
            session.close()
            _copy_screenshots(request, tmp_path)

    driver_fixture.__name__ = entry["fixture"]
    return pytest.fixture(name=entry["fixture"])(driver_fixture)


for _entry in json.loads(os.environ.get("HOTDOCS_DRIVERS", "[]")):
    globals()["_hotdocs_driver_" + _entry["fixture"]] = _make_driver_fixture(_entry)
'''


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _sha256(path):
    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _find_adapter(repo_root, prefix, name):
    module = name.replace("-", "_")
    rel = Path("gen") / f"{prefix}-{name}" / f"{prefix}_{module}.py"
    candidate = repo_root / rel
    if candidate.is_file():
        return candidate
    tool_root = _tool_root()
    if tool_root is not None and (tool_root / rel).is_file():
        return (tool_root / rel).absolute()
    return None


def _load_module(path, name):
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = previous


def _frontmatter_lines(path):
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return out


def _list_line(lines, key):
    for line in lines:
        if line.startswith(key + ":"):
            text = line.partition("[")[2].partition("]")[0]
            return [item.strip() for item in text.split(",") if item.strip()]
    return []


def _failure_text(name, exc):
    return f"{name} adapter failed: {type(exc).__name__}: {exc}"


@dataclass
class RunEnvironment:
    ok: bool
    failure_message: object
    interpreter: object
    assets: list
    drivers: list
    plugin_dir: object
    _asset_specs: list = field(default_factory=list, repr=False)
    _driver_specs: list = field(default_factory=list, repr=False)
    _repo_root: object = field(default=None, repr=False)
    _slug: object = field(default=None, repr=False)

    def pytest_args(self):
        return ["-p", PLUGIN_NAME]

    def driver_fixtures(self):
        return [fixture for _, fixture, _ in self._driver_specs]

    def env_for(self, code_dir):
        code_dir = Path(code_dir)
        repo_root = Path(self._repo_root).absolute()
        assets = [
            {
                "path": path,
                "file": str((code_dir / path).absolute()),
                "adapter": str(adapter),
            }
            for path, adapter in self._asset_specs
        ]
        drivers = [
            {
                "name": name,
                "fixture": fixture,
                "adapter": str(adapter),
                "repo_root": str(repo_root),
            }
            for name, fixture, adapter in self._driver_specs
        ]
        env = {
            "HOTDOCS_ASSETS": json.dumps(assets),
            "HOTDOCS_DRIVERS": json.dumps(drivers),
        }
        if self._slug is not None and code_dir.resolve() == (
            repo_root / "gen" / self._slug
        ).resolve():
            env["HOTDOCS_SCREENSHOTS"] = str(
                repo_root / ".hotdocs" / "screenshots" / self._slug
            )
        return env

    def close(self):
        if self.plugin_dir is not None:
            shutil.rmtree(self.plugin_dir, ignore_errors=True)
            self.plugin_dir = None

    def to_dict(self):
        return {
            "ok": self.ok,
            "failure_message": self.failure_message,
            "interpreter": self.interpreter,
            "assets": self.assets,
            "drivers": self.drivers,
            "plugin_dir": self.plugin_dir,
        }


def _prepare(repo_root, declared_assets, driver_names, slug):
    repo_root = Path(repo_root).absolute()
    arch = repo_root / "specs" / "architecture"

    kinds = ["python"] + list(dict.fromkeys(kind for kind, _ in declared_assets))
    kind_adapters = {kind: _find_adapter(repo_root, "kind", kind) for kind in kinds}

    def asset_entry(kind, path):
        adapter = kind_adapters[kind]
        return {
            "kind": kind,
            "path": path,
            "definition_sha256": _sha256(arch / f"asset-kind-{kind}.md"),
            "adapter_sha256": None if adapter is None else _sha256(adapter),
            "versions": {},
            "lockfile_sha256": None,
        }

    assets = [asset_entry("python", ".")] + [
        asset_entry(kind, path) for kind, path in declared_assets
    ]

    names = sorted(dict.fromkeys(driver_names))
    driver_adapters = {name: _find_adapter(repo_root, "driver", name) for name in names}
    drivers = [
        {
            "name": name,
            "definition_sha256": _sha256(arch / f"test-driver-{name}.md"),
            "adapter_sha256": None
            if driver_adapters[name] is None
            else _sha256(driver_adapters[name]),
            "versions": {},
            "lockfile_sha256": None,
        }
        for name in names
    ]

    failure = None
    interpreter = None
    for kind in kinds:
        adapter = kind_adapters[kind]
        if adapter is None:
            failure = f"unknown asset kind: {kind}"
            break
        try:
            module = _load_module(adapter, "kind_" + kind.replace("-", "_"))
            report = module.provision(repo_root)
        except Exception as exc:
            failure = _failure_text(kind, exc)
            break
        if not _get(report, "ok"):
            failure = _get(report, "reason")
            break
        for entry in assets:
            if entry["kind"] == kind:
                entry["versions"] = _get(report, "versions")
                entry["lockfile_sha256"] = _get(report, "lockfile_sha256")
        if kind == "python":
            interpreter = _get(report, "interpreter")

    driver_specs = []
    if failure is None:
        for entry in drivers:
            name = entry["name"]
            adapter = driver_adapters[name]
            if adapter is None:
                failure = f"unknown test driver: {name}"
                break
            try:
                module = _load_module(adapter, "driver_" + name.replace("-", "_"))
                fixture = module.FIXTURE
                report = module.provision(repo_root)
            except Exception as exc:
                failure = _failure_text(name, exc)
                break
            if not _get(report, "ok"):
                failure = _get(report, "reason")
                break
            entry["versions"] = _get(report, "versions")
            entry["lockfile_sha256"] = _get(report, "lockfile_sha256")
            driver_specs.append((name, fixture, adapter))

    asset_specs = [(path, kind_adapters[kind]) for kind, path in declared_assets]

    if failure is not None:
        return RunEnvironment(
            ok=False,
            failure_message=failure,
            interpreter=None,
            assets=assets,
            drivers=drivers,
            plugin_dir=None,
            _asset_specs=asset_specs,
            _driver_specs=driver_specs,
            _repo_root=repo_root,
            _slug=slug,
        )

    plugin_dir = tempfile.mkdtemp()
    (Path(plugin_dir) / f"{PLUGIN_NAME}.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
    return RunEnvironment(
        ok=True,
        failure_message=None,
        interpreter=interpreter,
        assets=assets,
        drivers=drivers,
        plugin_dir=plugin_dir,
        _asset_specs=asset_specs,
        _driver_specs=driver_specs,
        _repo_root=repo_root,
        _slug=slug,
    )


def prepare(component_id, repo_root):
    repo_root = Path(repo_root)
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    lines = _frontmatter_lines(repo_root / "specs" / "components" / slug / "component.md")
    declared_assets = []
    for item in _list_line(lines, "assets"):
        kind, _, path = item.partition(":")
        declared_assets.append((kind, path))
    return _prepare(repo_root, declared_assets, _list_line(lines, "drivers"), slug)


def prepare_capability(capability_id, repo_root):
    repo_root = Path(repo_root)
    driver_names = []
    for path in sorted((repo_root / "specs" / "product").glob("*.md")):
        lines = _frontmatter_lines(path)
        ids = [line.partition(":")[2].strip() for line in lines if line.startswith("id:")]
        if capability_id in ids:
            driver_names = _list_line(lines, "drivers")
            break
    return _prepare(repo_root, [], driver_names, None)
