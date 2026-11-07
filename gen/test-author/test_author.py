from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.util
import json
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROMPT_VERSION = "v1"
GATE_VERSION = "generated_test@1.0.0"


def _get(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _component_slug(component_id):
    component_id = component_id or ""
    return component_id[5:] if component_id.startswith("comp-") else component_id


def _module_import_statements(component_id, module_names):
    if module_names:
        return [f"import {name}" for name in module_names]
    slug = _component_slug(component_id)
    module_name = slug.replace("-", "_")
    return [f"import {module_name}"]


def _relative_output_path(component_id, criterion_id):
    slug = _component_slug(component_id)
    filename = f"test_{criterion_id.lower().replace('-', '_')}.py"
    return f"verification/{slug}/generated-test/{filename}"


def _output_path(repo_root, component_id, criterion_id):
    return Path(repo_root) / _relative_output_path(component_id, criterion_id)


def _write_file(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _hash_json(data):
    encoded = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _load_dependency_module(repo_root, slug, module_name):
    repo_root = Path(repo_root)
    base = repo_root / "gen" / slug
    flat_path = base / f"{module_name}.py"
    pkg_path = base / module_name / "__init__.py"
    if flat_path.is_file():
        path = flat_path
    elif pkg_path.is_file():
        path = pkg_path
    else:
        raise ImportError(f"cannot locate dependency module {module_name!r} for {slug!r} under {base}")

    key = str(path.resolve())
    existing = sys.modules.get(key)
    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(key, path)
    module = importlib.util.module_from_spec(spec)
    # A dataclass defined in the loaded module resolves sys.modules[__name__]
    # while its class body executes, so registration must happen before exec.
    sys.modules[key] = module
    spec.loader.exec_module(module)
    return module


def _extract_file_content(text, nonce):
    if not text:
        return None
    pattern = re.compile(
        r"-----BEGIN FILE " + re.escape(nonce) + r"-----\n(.*?)\n-----END FILE " + re.escape(nonce) + r"-----",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1)


_SIG_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*->")


def _parse_param_count(params_str):
    depth = 0
    parts = []
    current = ""
    for ch in params_str:
        if ch in "([{":
            depth += 1
            current += ch
        elif ch in ")]}":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())

    count = 0
    variadic = False
    for part in parts:
        if not part or part == "*":
            continue
        if part.startswith("**") or part.startswith("*"):
            variadic = True
            continue
        count += 1
    return count, variadic


def _iter_dep_interfaces(dependency_interfaces):
    if isinstance(dependency_interfaces, dict):
        return list(dependency_interfaces.items())
    try:
        return list(dependency_interfaces)
    except TypeError:
        return []


def _dependency_arities(dependency_interfaces):
    arities = {}
    for _dep_id, text in _iter_dep_interfaces(dependency_interfaces):
        if not text:
            continue
        for match in _SIG_RE.finditer(text):
            name, params = match.group(1), match.group(2)
            count, variadic = _parse_param_count(params)
            arities.setdefault(name, []).append((count, variadic))
    return arities


def _funcdef_arity(node):
    args = node.args
    count = len(getattr(args, "posonlyargs", [])) + len(args.args) + len(args.kwonlyargs)
    variadic = args.vararg is not None or args.kwarg is not None
    return count, variadic


def _collect_fake_signatures(tree):
    sigs = {}
    alias_targets = {}

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            count, variadic = _funcdef_arity(node)
            sigs.setdefault(node.name, []).append((count, variadic))
        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                alias_targets[node.targets[0].id] = node.value.id

    for alias, target in alias_targets.items():
        if target in sigs:
            sigs.setdefault(alias, []).extend(sigs[target])

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner = ast.parse(node.value)
            except SyntaxError:
                continue
            for inner_node in ast.walk(inner):
                if isinstance(inner_node, ast.FunctionDef):
                    count, variadic = _funcdef_arity(inner_node)
                    sigs.setdefault(inner_node.name, []).append((count, variadic))

    return sigs


def _check_fake_arity(tree, dependency_interfaces):
    dep_arities = _dependency_arities(dependency_interfaces)
    if not dep_arities:
        return None

    fake_sigs = _collect_fake_signatures(tree)
    for name, fake_arity_list in fake_sigs.items():
        if name not in dep_arities:
            continue
        dep_list = dep_arities[name]
        for f_count, f_variadic in fake_arity_list:
            matched = any(
                f_variadic or d_variadic or f_count == d_count
                for d_count, d_variadic in dep_list
            )
            if not matched:
                return {
                    "function": name,
                    "fake_arity": f_count,
                    "dependency_arities": dep_list,
                }
    return None


@dataclass
class TestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: Optional[dict]
    model_call_error: Optional[dict]


def _build_prompt(bundle, nonce):
    component_id = _get(bundle, "component_id", "") or ""
    criterion_id = _get(bundle, "criterion_id", "") or ""
    covers = _get(bundle, "covers", "") or ""
    criterion_text = _get(bundle, "criterion_text", "") or ""
    requirement_text = _get(bundle, "requirement_text", "") or ""
    interface_text = _get(bundle, "interface", "") or ""
    glossary_text = _get(bundle, "glossary", "") or ""
    dependency_interfaces = _get(bundle, "dependency_interfaces", {}) or {}
    module_names = _get(bundle, "module_names", []) or []

    import_block = "\n".join(_module_import_statements(component_id, module_names))

    dep_sections = []
    for dep_id, dep_interface in _iter_dep_interfaces(dependency_interfaces):
        dep_sections.append(f"### Dependency `{dep_id}`\n\n{dep_interface}")
    dep_block = "\n\n".join(dep_sections) if dep_sections else "(no declared dependencies)"

    return f"""You are authoring a single Python test file for one acceptance criterion.
You have no tool access and no file access. Answer using only the
information given below. You cannot read the target component's actual
`gen/` source code — only its public `interface/` contract, given below.

## Target component

Component id: {component_id}
Criterion id: {criterion_id}
Covers: {covers}

### Criterion (Given/When/Then)

{criterion_text}

### Covered requirement text ({covers})

{requirement_text}

### Target component interface

{interface_text}

### Glossary

{glossary_text}

### Dependency interfaces

{dep_block}

## How to import the component under test

{import_block}

The generator may lay the module out as a flat `<module>.py` file or as a
`<module>/` package directly under `gen/<component>/`; the import above
works identically either way. Do not infer the module name from a
function name or from the component id itself.

## How dependencies resolve at runtime, and how to fake them

No dependency of the component under test is statically importable.
Every dependency is resolved dynamically, at runtime, from:

  <repo_root>/gen/<dependency-slug>/<module_name>.py           (flat module)
  <repo_root>/gen/<dependency-slug>/<module_name>/__init__.py  (package)

This is never interceptable by name-based `sys.modules` injection or
`mock.patch`. To fake a dependency for a test, write a fake module file
under a fresh temporary `repo_root` directory — always as a flat module
(`<module_name>.py`), since every real loader checks the flat shape
first. `module_name` is the dependency's slug with hyphens replaced by
underscores — never `"__init__"`.

The component under test itself needs no custom loader for its own
code: it is imported with a plain `import <module_name>` statement,
exactly as shown above — never a dynamic loader.

The one correctness-critical step when a test writes a fake module and
loads it: the loaded module object MUST be registered in `sys.modules`
*before* `exec_module` is called on it — never after. A dataclass
defined in that module looks up `sys.modules[<module>.__name__]` while
its class body executes, so registering afterward breaks any module
that defines a dataclass:

```python
spec = importlib.util.spec_from_file_location(module_name, fake_path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module  # MUST happen before exec_module
spec.loader.exec_module(module)
```

## Dependency contracts — fakes MUST match them exactly

Each dependency's real, documented call signature and return shape is
given above under "Dependency interfaces". Any fake you write for a
dependency's behavior MUST match that documented signature and return
shape exactly — never invented, never simplified. Unlike the target
component (whose `gen/` source you never see — write only against its
interface above), a dependency's own contract is public and MUST be
honored precisely.

Worked example: if a dependency's documented return type has named
fields (e.g. `{{"text": ..., "model": ..., "backend": ..., "model_call_error": ...}}`),
your fake MUST return an object or dict exposing every one of those
fields — never a bare list, string, or number, even if the test you are
writing only reads one of them.

## Reading values the target component itself returns

Any field you read from a value the target component itself returns —
not only a faked dependency's data, including the target's own
top-level return value — MUST use dual dict-or-attribute access (e.g.
a small helper that tries `obj["field"]` then falls back to
`getattr(obj, "field")`), never a bare `.attr` access alone. Any
component in this corpus may legitimately return either a dict or an
object shape in a given round.

## Confirming a fake was actually invoked

Never assert a fake ran by reaching into `sys.modules` under a guessed
key — real loaders key dynamically (often qualified by `repo_root` or
a content hash), so any guessed key is unreliable and will fail even
against a correct candidate. To confirm a fake ran, make the fake
itself append an invocation record to a **file** (a path the test
itself controls and creates, e.g. under a temp directory) and assert
against that file's contents — never an in-process, module-level list,
since the test cannot reliably re-locate the module object that would
hold it either.

## Timestamp window assertions

If the test asserts a wall-clock "own write time" field falls within a
`[before, after]` window, truncate `before` and `after` to the same
precision the field's own documented format carries (e.g. whole
seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits)
before comparing — never compare a truncated-on-write timestamp
against microsecond-precision bounds directly.

## Synthetic fixtures (if the test constructs component.md /
## requirements / interface / acceptance / specs/vars / specs/decisions
## files on disk)

Every frontmatter-bearing document (`component.md`, `specs/vars/VAR-*.md`,
`specs/decisions/D<N>.md`) MUST carry frontmatter with at least `id`,
`title`, `status`, and `owners`; `status` MUST be exactly one of
`draft`, `ratified`, or `deprecated`. If `status: ratified`, also set a
placeholder `last_ratified_commit`. Every `requirements/` file needs a
matching `acceptance/` file with a `Covers:` tag. A unit file
(`constraints.md`, or anything under `requirements/`, `interface/`, or
`acceptance/`) carries NO frontmatter at all. Never `import yaml` or
any other not-already-installed third-party package in the test —
write and parse frontmatter as plain text.

Any list-valued frontmatter field (`owners`, `depends_on`, `realizes`,
`uses_var`) MUST use YAML flow style, e.g. `[a, b]` — never block
style; this corpus's frontmatter reader does not recognize block style
as a list.

A synthetic fixture component SHOULD default to `sealed: true` with a
short, fake `source_path` not under `gen/` — this exempts it from
`realizes` and the capability-linkage machinery entirely. Only give
the fixture a resolvable `P-<id>` under `realizes` if the criterion
being tested genuinely concerns `realizes`/capability-linkage
behavior.

If the criterion depends on a precondition the target checks against
`spec-linter`, call `lint()` against the fixture first and assert
there are zero hard-fail findings, before exercising the real behavior
under test. Call it exactly like this:

```python
lint(None, repo_root)
```

(`paths` first, positionally `None` — never a single positional
argument.)

## Output format

Wrap your test file's content exactly as:

-----BEGIN FILE {nonce}-----
<the complete, exact test file content, verbatim>
-----END FILE {nonce}-----

Output nothing else outside those markers — no narration, no code
fence, no preamble or postamble.
"""


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    if repo_root is None:
        repo_root = Path.cwd()
    repo_root = Path(repo_root)

    component_id = _get(bundle, "component_id", "") or ""
    criterion_id = _get(bundle, "criterion_id", "") or ""
    covers = _get(bundle, "covers", "") or ""
    criterion_text = _get(bundle, "criterion_text", "") or ""
    requirement_text = _get(bundle, "requirement_text", "") or ""
    interface_text = _get(bundle, "interface", "") or ""
    glossary_text = _get(bundle, "glossary", "") or ""
    dependency_interfaces = _get(bundle, "dependency_interfaces", {}) or {}
    module_names = _get(bundle, "module_names", []) or []

    cache_manager_mod = _load_dependency_module(repo_root, "cache-manager", "cache_manager")

    content_fields = {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": criterion_text,
        "requirement_text": requirement_text,
        "interface": interface_text,
        "glossary": glossary_text,
        "dependency_interfaces": dependency_interfaces,
        "module_names": list(module_names),
    }
    criterion_content_hash = _hash_json(content_fields)
    gate_inputs_hash = _hash_json({"seed": seed})

    cache_key = cache_manager_mod.CacheKey(
        spec_bundle_hash=criterion_content_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager_mod.get(cache_key, repo_root=repo_root)
    if isinstance(cached, cache_manager_mod.CachedResult):
        payload = _get(cached, "payload", {}) or {}
        file_info = _get(payload, "file", None)
        if file_info is not None:
            output_path = _output_path(repo_root, component_id, criterion_id)
            _write_file(output_path, _get(file_info, "content", "") or "")
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=True,
            file=file_info,
            model_call_error=None,
        )

    nonce = secrets.token_hex(16)
    prompt = _build_prompt(bundle, nonce)

    llm_endpoint_mod = _load_dependency_module(repo_root, "llm-endpoint", "llm_endpoint")
    response = llm_endpoint_mod.complete(prompt, model, backend=llm_backend)

    model_call_error = _get(response, "model_call_error", None)
    if model_call_error:
        error = {
            "category": _get(model_call_error, "category", "unknown"),
            "message": _get(model_call_error, "message", ""),
        }
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=error,
        )

    text = _get(response, "text", "") or ""
    extracted = _extract_file_content(text, nonce)
    if extracted is None:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={
                "category": "no_markers",
                "message": "No matching BEGIN/END FILE markers found in model response.",
            },
        )

    try:
        tree = ast.parse(extracted)
    except SyntaxError as exc:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={"category": "malformed_code", "message": f"SyntaxError: {exc}"},
        )

    mismatch = _check_fake_arity(tree, dependency_interfaces)
    if mismatch is not None:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={
                "category": "fake_signature_mismatch",
                "message": (
                    f"Function {mismatch['function']!r} has fake arity "
                    f"{mismatch['fake_arity']}, which matches none of the "
                    f"dependency's documented arities {mismatch['dependency_arities']}."
                ),
            },
        )

    relative_path = _relative_output_path(component_id, criterion_id)
    output_path = repo_root / relative_path
    file_info = {"path": relative_path, "content": extracted}

    cached_result = cache_manager_mod.CachedResult(
        gate_type="generated_test",
        payload={
            "component_id": component_id,
            "criterion_id": criterion_id,
            "model": model,
            "file": file_info,
        },
        stored_at=cache_manager_mod.now_iso(),
    )
    cache_manager_mod.put(cache_key, cached_result, repo_root=repo_root)

    _write_file(output_path, extracted)

    return TestAuthoringResult(
        component_id=component_id,
        criterion_id=criterion_id,
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        file=file_info,
        model_call_error=None,
    )


_USAGE = (
    "usage: hotdocs author-test <component-id> <criterion-id> "
    "--model=<model-id> [--seed=<n>] [--repo-root=<dir>] [--format=json|text]\n"
)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] != "author-test":
        sys.stderr.write(_USAGE)
        return 2

    args = argv[1:]
    positional = []
    model = None
    seed = 0
    repo_root = Path.cwd()
    fmt = "text"

    for arg in args:
        if arg.startswith("--model="):
            model = arg[len("--model="):]
        elif arg.startswith("--seed="):
            try:
                seed = int(arg[len("--seed="):])
            except ValueError:
                sys.stderr.write("invalid --seed value\n")
                return 2
        elif arg.startswith("--repo-root="):
            repo_root = Path(arg[len("--repo-root="):])
        elif arg.startswith("--format="):
            fmt = arg[len("--format="):]
            if fmt not in ("json", "text"):
                sys.stderr.write("invalid --format value\n")
                return 2
        elif arg.startswith("--"):
            sys.stderr.write(f"unknown option: {arg}\n")
            return 2
        else:
            positional.append(arg)

    if len(positional) != 2 or model is None:
        sys.stderr.write(_USAGE)
        return 2

    component_id, criterion_id = positional

    try:
        assembler_mod = _load_dependency_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
        bundle = assembler_mod.assemble_criterion(component_id, criterion_id, repo_root)
    except Exception as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    result = author_test(bundle, model, seed, repo_root=repo_root)

    error = _get(result, "model_call_error", None)

    if fmt == "json":
        sys.stdout.write(json.dumps(dataclasses.asdict(result), indent=2) + "\n")
    else:
        if error:
            sys.stdout.write(f"model_call_error: {error}\n")
        else:
            file_info = _get(result, "file", None)
            path = _get(file_info, "path", None) if file_info else None
            cache_hit = _get(result, "cache_hit", False)
            sys.stdout.write(f"wrote {path} (cache_hit={cache_hit})\n")

    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())