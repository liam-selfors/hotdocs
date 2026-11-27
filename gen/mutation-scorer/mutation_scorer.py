"""Mutation scorer: measures how strong a component's passing tests are."""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

BASELINE_TIMEOUT = 300

_JS_PATTERN = re.compile(r"\bfunction\s*[\w$]*\s*\(|=>|\b(const|let)\s")


@dataclass
class MutationResult:
    mutation_score: float | None
    mutation_error: str | None
    faulty_tests: list = field(default_factory=list)
    mutants: int = 0
    killed: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class _AdapterFailure(Exception):
    def __init__(self, kind: str, exc: BaseException):
        super().__init__(f"{kind} adapter failed: {type(exc).__name__}: {exc}")
        self.message = str(self)


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load_adapter(kind: str, repo_root: Path):
    module = "kind_" + kind.replace("-", "_")
    rel = Path("gen") / f"kind-{kind}" / f"{module}.py"
    path = Path(repo_root) / rel
    if not path.exists():
        path = _tool_root() / rel
    spec = importlib.util.spec_from_file_location(module, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module] = mod
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
    return mod


def _py_files(code_dir: Path) -> list[tuple[str, Path]]:
    files = []
    for path in code_dir.rglob("*.py"):
        rel = path.relative_to(code_dir)
        if "__pycache__" in rel.parts:
            continue
        files.append(("/".join(rel.parts), path))
    files.sort(key=lambda item: item[0])
    return files


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def _javascript_error(code_dir: Path) -> str | None:
    for rel, path in _py_files(code_dir):
        tree = ast.parse(path.read_bytes(), filename=str(path))
        docstrings = _docstring_ids(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in docstrings:
                continue
            text = node.value
            if len(text) >= 200 and _JS_PATTERN.search(text) and (";" in text or "{" in text):
                return (
                    f"javascript in a string at {rel}:{node.lineno}; "
                    "declare it as an asset (specs/architecture/asset-kinds.md)"
                )
    return None


def _descendants(pid: int) -> list[int]:
    out = subprocess.run(
        ["ps", "-eo", "pid=,ppid="], capture_output=True, text=True
    ).stdout
    children: dict[int, list[int]] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        child, parent = int(parts[0]), int(parts[1])
        children.setdefault(parent, []).append(child)
    found = []
    queue = [pid]
    while queue:
        current = queue.pop(0)
        for child in children.get(current, []):
            if child not in found:
                found.append(child)
                queue.append(child)
    return found


def _kill_tree(proc: subprocess.Popen) -> None:
    for pid in reversed(_descendants(proc.pid)):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    proc.wait()


def _snapshot(code_dir: Path) -> dict[Path, bytes]:
    snap = {}
    for path in code_dir.rglob("*"):
        if path.is_file() and "__pycache__" not in path.relative_to(code_dir).parts:
            snap[path] = path.read_bytes()
    return snap


def _restore(snap: dict[Path, bytes]) -> None:
    for path, data in snap.items():
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)


def _baseline_message(code, timed_out) -> str:
    if timed_out:
        return f"mutation baseline timed out in the sandbox after {BASELINE_TIMEOUT} seconds"
    return f"mutation baseline failed in the sandbox: pytest exited {code}"


def score(component_id: str, repo_root: Path, tests: list[str], environment) -> MutationResult:
    if not tests:
        return MutationResult(None, None, [], 0, 0)
    tmp = None
    faulty: list[str] = []
    counts = {"mutants": 0, "killed": 0}
    try:
        repo_root = Path(repo_root)
        slug = _slug(component_id)
        tmp = Path(tempfile.mkdtemp())
        gen_dir = tmp / "gen"
        gen_dir.mkdir()
        copy = gen_dir / slug
        shutil.copytree(
            repo_root / "gen" / slug, copy, ignore=shutil.ignore_patterns("__pycache__")
        )
        for entry in sorted((repo_root / "gen").iterdir()):
            if entry.is_dir() and entry.name != slug:
                os.symlink(entry, gen_dir / entry.name)

        js_error = _javascript_error(copy)
        if js_error is not None:
            return MutationResult(None, js_error, [], 0, 0)

        interpreter = _get(environment, "interpreter")
        plugin_dir = _get(environment, "plugin_dir")
        pytest_args = list(_get(environment, "pytest_args")())
        env = dict(os.environ)
        env.update(_get(environment, "env_for")(copy))
        env["PYTHONPATH"] = str(copy) + os.pathsep + str(plugin_dir)
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        def run(run_tests, timeout):
            cmd = [
                str(interpreter), "-m", "pytest", "--noconftest",
                "-p", "no:cacheprovider", *pytest_args, *run_tests,
            ]
            start = time.monotonic()
            proc = subprocess.Popen(
                cmd, cwd=str(copy), env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                return None, True, time.monotonic() - start
            return code, False, time.monotonic() - start

        run_tests = list(tests)
        code, timed_out, elapsed = run(run_tests, BASELINE_TIMEOUT)
        if timed_out or code != 0:
            first_message = _baseline_message(code, timed_out)
            for test in tests:
                t_code, t_out, _ = run([test], BASELINE_TIMEOUT)
                if t_out or t_code != 0:
                    faulty.append(test)
            if not faulty:
                return MutationResult(None, first_message, [], 0, 0)
            run_tests = [t for t in tests if t not in faulty]
            if not run_tests:
                return MutationResult(None, None, faulty, 0, 0)
            code, timed_out, elapsed = run(run_tests, BASELINE_TIMEOUT)
            if timed_out or code != 0:
                return MutationResult(None, _baseline_message(code, timed_out), faulty, 0, 0)

        mutant_timeout = max(2.0, 10 * elapsed)
        snap = _snapshot(copy)

        targets = [("python", copy)]
        for asset in list(_get(environment, "assets") or [])[1:]:
            targets.append((_get(asset, "kind"), copy / _get(asset, "path")))

        try:
            for kind, target in targets:
                adapter = _load_adapter(kind, repo_root)
                try:
                    sites = list(adapter.strength_sites(target))
                except Exception as exc:
                    raise _AdapterFailure(kind, exc)
                for site in sites:
                    try:
                        try:
                            adapter.apply_site(target, site)
                        except Exception as exc:
                            raise _AdapterFailure(kind, exc)
                        m_code, m_out, _ = run(run_tests, mutant_timeout)
                        counts["mutants"] += 1
                        if m_out or m_code != 0:
                            counts["killed"] += 1
                    finally:
                        _restore(snap)
        except _AdapterFailure as failure:
            return MutationResult(
                None, failure.message, faulty, counts["mutants"], counts["killed"]
            )

        mutants, killed = counts["mutants"], counts["killed"]
        value = killed / mutants if mutants else 1.0
        return MutationResult(value, None, faulty, mutants, killed)
    except Exception as exc:
        return MutationResult(
            None,
            f"mutation run failed: {type(exc).__name__}: {exc}",
            faulty,
            counts["mutants"],
            counts["killed"],
        )
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
