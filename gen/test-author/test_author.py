"""test-author: authors one generated-test criterion's test file from spec prose alone."""

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import secrets
import sys
from pathlib import Path

PROMPT_VERSION = "v1"
GATE_VERSION = "generated_test@1.0.0"
GATE_TYPE = "generated_test"


# ---------------------------------------------------------------------------
# Prompt blocks (specs/architecture/test-author-prompt.md), verbatim.
# ---------------------------------------------------------------------------

_BLOCKS = [
    """The component under test itself needs no custom loader: a plain `import @MODULE@`.
Its own dependencies are resolved differently. No dependency is statically importable: each is loaded at runtime from `<repo_root>/gen/<dependency-slug>/<module_name>.py` (flat) or `<repo_root>/gen/<dependency-slug>/<module_name>/__init__.py` (package), else from the tool's own copy, so omitting one never makes it missing.
A dependency is never interceptable by name-based `sys.modules` injection or `mock.patch`.
To fake a dependency, write a fake module file under a fresh temporary `repo_root`, always in flat-module shape: `<repo_root>/gen/<dependency-slug>/<module_name>.py`. Every real loader checks flat first.
`module_name` is the slug with hyphens replaced by underscores, never `"__init__"`.
Whenever a test loads a module from a file path itself, it uses exactly this shape, with `sys.modules[module_name] = module` before `spec.loader.exec_module(module)`, which a dataclass needs:

    import importlib.util
    import sys

    def load_module(path, module_name):
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module""",
    """Any fake a test writes for a dependency's behavior MUST match that dependency's real, documented call signature and return shape exactly, as its interface above gives them, never invented or simplified.
Given a documented return type with named fields, a fake MUST return every field, never a bare list, string or number in its place, even when the test reads only one field. For a dependency that documents

    bar_get(key: str) -> Entry
    Entry: {"key": str, "value": str, "stored_at": str}

a correct fake is

    def bar_get(key):
        return {"key": key, "value": "v", "stored_at": "2026-01-01T00:00:00Z"}

and a fake whose body is `return "v"` is wrong.""",
    """When a test builds a synthetic spec corpus (a fixture) under a temporary `repo_root`:
- Every frontmatter-bearing document it builds (`component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) carries `id`, `title`, `status` and `owners`, always, with `status` exactly one of `draft`, `ratified` or `deprecated`.
- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`.
- Every `requirements/` file of every fixture component has a matching `acceptance/` file with a `Covers:` tag.
- A unit file (`constraints.md`, or anything under `requirements/`, `interface/` or `acceptance/`) carries no frontmatter at all.
- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text.""",
    """- A fixture component defaults to `sealed: true` with a short, fake `source_path` not under `gen/`, such as `source_path: legacy/foo/`, unless the criterion concerns `realizes` or capability linkage: sealed exempts it from `realizes` and the capability machinery.
- Only a criterion that needs `realizes`-driven behavior has the fixture supply a resolvable `P-<id>`.""",
    """- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) uses YAML flow style, such as `owners: [a, b]`, never block style (`- a` lines), which the frontmatter reader does not read as a list.""",
    """- When the criterion depends on a precondition the target checks with `spec-linter`, the test calls `lint()` on the fixture first and asserts zero hard failures before exercising the behavior under test. The call is exactly `lint(None, repo_root)`: `paths` first and positionally `None`, never one positional argument.

    import importlib.util
    import sys
    from pathlib import Path
    import @MODULE@

    gen = next(p for p in Path(@MODULE@.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0""",
    """Every field read from a value the target itself returns, not only a faked dependency's data, MUST use dual dict-or-attribute access, never one assumed shape:

    def field(value, name):
        return value[name] if isinstance(value, dict) else getattr(value, name)""",
    """A test MUST NEVER assert a fake was used by reaching into `sys.modules` under a guessed key: real loaders key modules dynamically, often by `repo_root` or a hash, so any guess is unreliable.""",
    """A test asserting that a wall-clock "own write time" field falls within a `[before, after]` window truncates `before` and `after` to the precision of the field's documented format, such as whole seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits (`datetime.now(timezone.utc).replace(microsecond=0)`), never comparing a timestamp truncated on write against microsecond-precision bounds.""",
    """To confirm a fake ran, the fake's own code appends one line per call to a log file at a path the test controls, and the test reads that file; never an in-process, module-level list, since the test cannot reliably find the module object that wrote it.
A test builds the source of any file it writes by concatenating strings, with `repr()` for every value it embeds, never with `str.format`, `%` or an f-string over text that holds braces or percent signs.""",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _bget(bundle, name):
    if isinstance(bundle, dict):
        return bundle.get(name)
    return getattr(bundle, name, None)


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _module_names(bundle):
    names = _bget(bundle, "module_names") or []
    if names:
        return list(names)
    return [_slug(_bget(bundle, "component_id") or "").replace("-", "_")]


def _filename(criterion_id):
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_dep(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / (module_name + ".py")
    if not path.is_file():
        path = base / module_name / "__init__.py"
    key = "_test_author_dep_" + module_name + "_" + _sha(str(path.resolve()))[:16]
    spec = importlib.util.spec_from_file_location(key, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


def _with_header(bundle, content):
    criterion_text = _bget(bundle, "criterion_text") or ""
    requirement_text = _bget(bundle, "requirement_text") or ""
    header = "# hotdocs-criterion: sha256:" + _sha(criterion_text + "\n" + requirement_text)
    first, sep, rest = content.partition("\n")
    if first.startswith("# hotdocs-criterion:"):
        content = rest
    return header + "\n" + content


def _build_prompt(bundle, nonce):
    modules = _module_names(bundle)
    module = modules[0]
    parts = [
        "You are writing one Python pytest test file for one acceptance criterion "
        "of a software component, from its specification alone. You have no access "
        "to the component's implementation.",
        "You have no tool or file access: answer from this bundle alone.",
        "Wrap your test file's content exactly as:\n\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----",
        "The test must exercise the component's public interface as described, "
        "asserting the criterion's Then clause.",
        "The module(s) under test, each imported with exactly this statement:\n\n"
        + "\n".join("import " + name for name in modules),
    ]
    parts.extend(block.replace("@MODULE@", module) for block in _BLOCKS)
    parts.append("## Component\n\n" + str(_bget(bundle, "component_id") or ""))
    parts.append("## Criterion " + str(_bget(bundle, "criterion_id") or "") + "\n\n"
                 + "Covers: " + str(_bget(bundle, "covers") or "") + "\n\n"
                 + str(_bget(bundle, "criterion_text") or ""))
    parts.append("## Covered requirement\n\n" + str(_bget(bundle, "requirement_text") or ""))
    parts.append("## Interface\n\n" + str(_bget(bundle, "interface") or ""))
    dep_interfaces = _bget(bundle, "dependency_interfaces") or {}
    if dep_interfaces:
        entries = ["### " + dep_id + "\n" + text for dep_id, text in dep_interfaces.items()]
        parts.append("## Dependency interfaces\n\n" + "\n\n".join(entries))
    parts.append("## Glossary\n\n" + str(_bget(bundle, "glossary") or ""))
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Static validation (R-AUTHOR-020)
# ---------------------------------------------------------------------------

_SIG_RE = re.compile(r"\b([A-Za-z_]\w*)\(([^()]*)\)\s*->")


def _split_params(text):
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _dep_signatures(dep_interfaces):
    sigs = {}
    for text in dep_interfaces.values():
        for match in _SIG_RE.finditer(text or ""):
            params = [p for p in _split_params(match.group(2)) if p not in ("*", "/")]
            arity = None if any(p.startswith("*") for p in params) else len(params)
            sigs.setdefault(match.group(1), set()).add(arity)
    return sigs


def _fn_arity(fn):
    a = fn.args
    if a.vararg or a.kwarg:
        return None
    return len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs)


def _check_tree(tree, sigs):
    defs = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs[node.name] = _fn_arity(node)
    candidates = list(defs.items())
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name) and node.value.id in defs):
            candidates.append((node.targets[0].id, defs[node.value.id]))
    for name, arity in candidates:
        if name in sigs and arity is not None:
            expected = sigs[name]
            if None not in expected and arity not in expected:
                return name, arity, expected
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                sub = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            found = _check_tree(sub, sigs)
            if found:
                return found
    return None


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def _result(bundle, model, seed, cache_hit, file, error):
    return {
        "component_id": _bget(bundle, "component_id"),
        "criterion_id": _bget(bundle, "criterion_id"),
        "model": model,
        "seed": seed,
        "prompt_version": PROMPT_VERSION,
        "cache_hit": cache_hit,
        "file": file,
        "model_call_error": error,
    }


def _write(repo_root, rel_path, content):
    target = Path(repo_root) / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content.encode("utf-8"))


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
    component_id = _bget(bundle, "component_id") or ""
    criterion_id = _bget(bundle, "criterion_id") or ""
    dep_interfaces = _bget(bundle, "dependency_interfaces") or {}
    rel_path = "verification/" + _slug(component_id) + "/generated-test/" + _filename(criterion_id)

    criterion_hash = "sha256:" + _sha(json.dumps({
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": _bget(bundle, "covers"),
        "criterion_text": _bget(bundle, "criterion_text"),
        "requirement_text": _bget(bundle, "requirement_text"),
        "interface": _bget(bundle, "interface"),
        "glossary": _bget(bundle, "glossary"),
    }, sort_keys=True))
    gate_inputs_hash = "sha256:" + _sha(json.dumps({
        "seed": seed,
        "prompt_version": PROMPT_VERSION,
        "dependency_interfaces": dict(dep_interfaces),
        "module_names": _module_names(bundle),
    }, sort_keys=True))

    cache_manager = _load_dep("cache-manager", "cache_manager", repo_root)
    key = cache_manager.CacheKey(
        spec_bundle_hash=criterion_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin=model,
    )
    cached = cache_manager.get(key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        cached_file = _field(_field(cached, "payload"), "file")
        content = _with_header(bundle, _field(cached_file, "content"))
        _write(repo_root, rel_path, content)
        return _result(bundle, model, seed, True, {"path": rel_path, "content": content}, None)

    llm_endpoint = _load_dep("llm-endpoint", "llm_endpoint", repo_root)
    nonce = secrets.token_hex(16)
    response = llm_endpoint.complete(_build_prompt(bundle, nonce), model, backend=llm_backend)
    error = _field(response, "model_call_error")
    if error:
        return _result(bundle, model, seed, False, None, error)

    match = re.search(
        "-----BEGIN FILE " + nonce + "-----\n?(.*?)\n?-----END FILE " + nonce + "-----",
        _field(response, "text"),
        re.DOTALL,
    )
    if not match:
        return _result(bundle, model, seed, False, None, {
            "category": "missing_file_markers",
            "message": "response holds no matching BEGIN/END FILE marker pair",
        })
    extracted = match.group(1)

    try:
        tree = ast.parse(extracted)
    except SyntaxError as exc:
        return _result(bundle, model, seed, False, None, {
            "category": "malformed_code",
            "message": "authored test is not valid Python: " + str(exc.msg),
        })

    mismatch = _check_tree(tree, _dep_signatures(dep_interfaces))
    if mismatch:
        name, arity, expected = mismatch
        return _result(bundle, model, seed, False, None, {
            "category": "fake_signature_mismatch",
            "message": "fake " + name + " takes " + str(arity)
                       + " parameter(s); its dependency interface documents "
                       + " or ".join(str(n) for n in sorted(expected)),
        })

    content = _with_header(bundle, extracted)
    file = {"path": rel_path, "content": content}
    cache_manager.put(key, cache_manager.CachedResult(
        gate_type=GATE_TYPE,
        payload={
            "component_id": component_id,
            "criterion_id": criterion_id,
            "model": model,
            "file": file,
            "seed": seed,
            "prompt_version": PROMPT_VERSION,
        },
        stored_at=cache_manager.now_iso(),
    ), repo_root=repo_root)
    _write(repo_root, rel_path, content)
    return _result(bundle, model, seed, False, file, None)


# ---------------------------------------------------------------------------
# CLI: hotdocs author-test <component-id> <criterion-id> --model=<id> ...
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(prog="hotdocs author-test")
    parser.add_argument("component_id")
    parser.add_argument("criterion_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    repo_root = Path(args.repo_root)
    assembler = _load_dep("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    bundle = assembler.assemble_criterion(args.component_id, args.criterion_id, repo_root)
    result = author_test(bundle, args.model, args.seed, repo_root=repo_root)
    error = result["model_call_error"]
    if args.format == "json":
        print(json.dumps(result))
    elif error:
        print("model_call_error: " + str(_field(error, "category")) + ": " + str(_field(error, "message")))
    else:
        print(result["file"]["path"])
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
