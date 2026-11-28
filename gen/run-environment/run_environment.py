"""Run environment: provisions asset kinds and test drivers, writes the pytest plugin."""

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

PLUGIN_MODULE = "hotdocs_run_plugins"

PLUGIN_SOURCE = '''"""pytest plugin written by run-environment: asset_runner and driver fixtures."""

import importlib.util
import json
import os
import shutil
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


def _copy_screenshots(request, tmp_path):
    target = os.environ.get("HOTDOCS_SCREENSHOTS")
    if not target:
        return
    dest = Path(target) / Path(str(request.path)).stem
    for png in sorted((tmp_path / "screenshots").glob("*.png")):
        try:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(png), str(dest / png.name))
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

    return pytest.fixture(name=entry["fixture"])(driver_fixture)


for _entry in json.loads(os.environ.get("HOTDOCS_DRIVERS", "[]")):
    globals()["hotdocs_driver_" + _entry["fixture"].replace("-", "_")] = _make_driver_fixture(_entry)
'''


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _sha256(path):
    if path is None or not Path(path).is_file():
        return None
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _find_adapter(repo_root: Path, prefix: str, name: str):
    rel = Path("gen") / f"{prefix}-{name}" / f"{prefix}_{name.replace('-', '_')}.py"
    for base in (repo_root, _tool_root()):
        candidate = base / rel
        if candidate.is_file():
            return candidate
    return None


def _load(path: Path):
    name = path.stem
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _provision(label: str, adapter: Path, repo_root: Path):
    """Return (module, report, failure_message)."""
    try:
        module = _load(adapter)
        report = module.provision(repo_root)
    except Exception as exc:
        return None, None, f"{label} adapter failed: {type(exc).__name__}: {exc}"
    if not _get(report, "ok"):
        return module, report, _get(report, "reason")
    return module, report, None


def _frontmatter(path: Path) -> list:
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


def _list_line(lines: list, key: str) -> list:
    for line in lines:
        if line.startswith(key + ":"):
            inner = line[line.index("[") + 1 : line.index("]")]
            return [item.strip() for item in inner.split(",") if item.strip()]
    return []


@dataclass
class RunEnvironment:
    ok: bool
    failure_message: str | None
    interpreter: str | None
    assets: list
    drivers: list
    plugin_dir: str | None
    _asset_adapters: list = field(default_factory=list, repr=False, compare=False)
    _driver_env: list = field(default_factory=list, repr=False, compare=False)
    _gen_dir: Path | None = field(default=None, repr=False, compare=False)
    _screenshots_dir: str | None = field(default=None, repr=False, compare=False)

    def pytest_args(self) -> list:
        return ["-p", PLUGIN_MODULE]

    def driver_fixtures(self) -> list:
        return [entry["fixture"] for entry in self._driver_env]

    def env_for(self, code_dir) -> dict:
        base = Path(os.path.abspath(code_dir))
        env = {
            "HOTDOCS_ASSETS": json.dumps(
                [
                    {"path": path, "file": str(base / path), "adapter": os.path.abspath(adapter)}
                    for path, adapter in self._asset_adapters
                ]
            ),
            "HOTDOCS_DRIVERS": json.dumps(self._driver_env),
        }
        if self._gen_dir is not None and Path(code_dir).resolve() == self._gen_dir.resolve():
            env["HOTDOCS_SCREENSHOTS"] = self._screenshots_dir
        return env

    def close(self) -> None:
        if self.plugin_dir is not None and os.path.isdir(self.plugin_dir):
            shutil.rmtree(self.plugin_dir)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "failure_message": self.failure_message,
            "interpreter": self.interpreter,
            "assets": self.assets,
            "drivers": self.drivers,
            "plugin_dir": self.plugin_dir,
        }


def _build(repo_root: Path, declared_assets: list, declared_drivers: list) -> RunEnvironment:
    arch = repo_root / "specs" / "architecture"
    kinds = ["python"]
    for kind, _ in declared_assets:
        if kind not in kinds:
            kinds.append(kind)

    failure = None
    interpreter = None
    kind_info = {}
    for kind in kinds:
        adapter = _find_adapter(repo_root, "kind", kind)
        info = {"adapter": adapter, "versions": {}, "lockfile_sha256": None}
        kind_info[kind] = info
        if failure is not None:
            continue
        if adapter is None:
            failure = f"unknown asset kind: {kind}"
            continue
        _, report, failure = _provision(kind, adapter, repo_root)
        if report is not None:
            info["versions"] = _get(report, "versions", {})
            info["lockfile_sha256"] = _get(report, "lockfile_sha256")
            if kind == "python":
                interpreter = _get(report, "interpreter")

    def asset_entry(kind, path):
        info = kind_info[kind]
        return {
            "kind": kind,
            "path": path,
            "definition_sha256": _sha256(arch / f"asset-kind-{kind}.md"),
            "adapter_sha256": _sha256(info["adapter"]),
            "versions": info["versions"],
            "lockfile_sha256": info["lockfile_sha256"],
        }

    assets = [asset_entry("python", ".")]
    assets += [asset_entry(kind, path) for kind, path in declared_assets]

    drivers = []
    driver_env = []
    for name in sorted(declared_drivers):
        adapter = _find_adapter(repo_root, "driver", name)
        entry = {
            "name": name,
            "definition_sha256": _sha256(arch / f"test-driver-{name}.md"),
            "adapter_sha256": _sha256(adapter),
            "versions": {},
            "lockfile_sha256": None,
        }
        drivers.append(entry)
        if failure is not None:
            continue
        if adapter is None:
            failure = f"unknown test driver: {name}"
            continue
        module, report, failure = _provision(name, adapter, repo_root)
        if report is not None:
            entry["versions"] = _get(report, "versions", {})
            entry["lockfile_sha256"] = _get(report, "lockfile_sha256")
        if failure is None:
            driver_env.append(
                {
                    "name": name,
                    "fixture": module.FIXTURE,
                    "adapter": os.path.abspath(adapter),
                    "repo_root": os.path.abspath(repo_root),
                }
            )

    ok = failure is None
    plugin_dir = None
    if ok:
        plugin_dir = tempfile.mkdtemp()
        (Path(plugin_dir) / f"{PLUGIN_MODULE}.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
    else:
        interpreter = None

    return RunEnvironment(
        ok=ok,
        failure_message=failure,
        interpreter=interpreter,
        assets=assets,
        drivers=drivers,
        plugin_dir=plugin_dir,
        _asset_adapters=[(path, kind_info[kind]["adapter"]) for kind, path in declared_assets],
        _driver_env=driver_env,
    )


def prepare(component_id: str, repo_root: Path) -> RunEnvironment:
    repo_root = Path(repo_root)
    slug = component_id.removeprefix("comp-")
    screenshots = Path(os.path.abspath(repo_root)) / ".hotdocs" / "screenshots" / slug
    if screenshots.exists():
        shutil.rmtree(screenshots)
    lines = _frontmatter(repo_root / "specs" / "components" / slug / "component.md")
    declared_assets = [tuple(item.split(":", 1)) for item in _list_line(lines, "assets")]
    env = _build(repo_root, declared_assets, _list_line(lines, "drivers"))
    env._gen_dir = repo_root / "gen" / slug
    env._screenshots_dir = str(screenshots)
    return env


def prepare_capability(capability_id: str, repo_root: Path) -> RunEnvironment:
    repo_root = Path(repo_root)
    lines = []
    for path in sorted((repo_root / "specs" / "product").glob("*.md")):
        candidate = _frontmatter(path)
        if any(line.startswith("id:") and line[3:].strip() == capability_id for line in candidate):
            lines = candidate
            break
    return _build(repo_root, [], _list_line(lines, "drivers"))
