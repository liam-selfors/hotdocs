"""Supplies one generated-test criterion's test, ready to run."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

_TRANSIENT = ("network", "timeout", "rate_limit")


@dataclass
class SuppliedTest:
    criterion_id: str
    path: str | None
    authored: bool
    test_authoring: dict | None
    failure_origin: str | None
    failure_message: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load(repo_root: Path, slug: str, name: str):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    package = base / name / "__init__.py"
    if package.is_file():
        spec = importlib.util.spec_from_file_location(
            name, package, submodule_search_locations=[str(base / name)])
    else:
        spec = importlib.util.spec_from_file_location(name, base / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _filename(criterion_id: str) -> str:
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _committed_path(component_id: str, criterion_id: str, repo_root: Path) -> Path:
    return (Path(repo_root) / "verification" / _slug(component_id)
            / "generated-test" / _filename(criterion_id))


def _header(bundle) -> str:
    payload = json.dumps(
        {key: _get(bundle, key) for key in
         ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"# hotdocs-criterion: sha256:{digest}"


def _error_kinds(report) -> str:
    kinds = []
    for finding in _get(report, "findings") or []:
        if _get(finding, "severity") == "error":
            kind = _get(finding, "kind")
            if kind not in kinds:
                kinds.append(kind)
    return ", ".join(kinds)


def supply(component_id: str, criterion_id: str, repo_root: Path, *, test_author=None,
           interpreter: str | None = None, assets: list[str] = (),
           drivers: list[str] = ()) -> SuppliedTest:
    assembler = _load(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
    prober = _load(repo_root, "test-probe", "test_probe")
    bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    module_name = _slug(component_id).replace("-", "_")

    def run_probe(source):
        return prober.probe(source, bundle, module_name, interpreter=interpreter,
                            assets=list(assets), drivers=list(drivers))

    committed = _committed_path(component_id, criterion_id, repo_root)
    if committed.is_file():
        source = committed.read_text(encoding="utf-8")
        lines = source.splitlines()
        if lines and lines[0] == _header(bundle):
            if _get(run_probe(source), "ok"):
                return SuppliedTest(criterion_id, str(committed), False, None, None, None)

    if test_author is None:
        return SuppliedTest(criterion_id, None, False, None, "test",
                            "test authoring failed: none: no test author")

    result = None
    for attempt in range(2):
        result = test_author(bundle)
        error = _get(result, "model_call_error")
        if not error or _get(error, "category") not in _TRANSIENT:
            break
    authoring = {key: _get(result, key)
                 for key in ("model", "seed", "prompt_version", "cache_hit")}
    error = _get(result, "model_call_error")
    if error:
        return SuppliedTest(
            criterion_id, None, True, authoring, "test",
            f"test authoring failed: {_get(error, 'category')}: {_get(error, 'message')}")

    content = _get(_get(result, "file"), "content")
    path = Path(tempfile.mkdtemp()) / _filename(criterion_id)
    path.write_text(content, encoding="utf-8")
    report = run_probe(content)
    if _get(report, "ok"):
        return SuppliedTest(criterion_id, str(path), True, authoring, None, None)
    return SuppliedTest(criterion_id, None, True, authoring, "test",
                        f"test failed its probe: {_error_kinds(report)}")


def discard(component_id: str, criterion_id: str, repo_root: Path) -> None:
    committed = _committed_path(component_id, criterion_id, repo_root)
    if committed.exists():
        committed.unlink()
