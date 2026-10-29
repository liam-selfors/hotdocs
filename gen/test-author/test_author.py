"""Authors the test code for one generated-test acceptance criterion."""

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import secrets
import sys
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional

PROMPT_VERSION = "v1"
GATE_VERSION = "generated_test@1.0.0"


@dataclass
class FileOutput:
    path: str
    content: str


@dataclass
class TestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: Optional[FileOutput]
    model_call_error: Optional[dict]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _load_dependency(slug: str, module_name: str, repo_root: Path):
    base = Path(repo_root) / "gen" / slug
    flat_path = base / f"{module_name}.py"
    pkg_path = base / module_name / "__init__.py"
    if flat_path.exists():
        load_path = flat_path
    elif pkg_path.exists():
        load_path = pkg_path
    else:
        raise ImportError(f"dependency '{slug}' not found under {base}")

    spec = importlib.util.spec_from_file_location(module_name, load_path)
    module = importlib.util.module_from_spec(spec)
    # A dataclass's class body resolves sys.modules[__module__] while it
    # executes, so registration MUST happen before exec_module.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _criterion_content_hash(bundle: Any) -> str:
    payload = {
        "component_id": _get(bundle, "component_id"),
        "criterion_id": _get(bundle, "criterion_id"),
        "covers": _get(bundle, "covers"),
        "criterion_text": _get(bundle, "criterion_text"),
        "requirement_text": _get(bundle, "requirement_text"),
        "interface": _get(bundle, "interface"),
        "glossary": _get(bundle, "glossary"),
        "dependency_interfaces": _get(bundle, "dependency_interfaces", {}) or {},
    }
    blob = json.dumps(payload, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _gate_inputs_hash(seed: int) -> str:
    blob = json.dumps({"prompt_version": PROMPT_VERSION, "seed": seed}, sort_keys=True)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _output_path(component_id: str, criterion_id: str) -> str:
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    filename = "test_" + criterion_id.lower().replace("-", "_") + ".py"
    return f"verification/{slug}/generated-test/{filename}"


def _write_file(repo_root: Path, rel_path: str, content: str) -> None:
    full = Path(repo_root) / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


def _split_params(args_str: str):
    parts = []
    depth = 0
    cur = ""
    for ch in args_str:
        if ch in "([{":
            depth += 1
            cur += ch
        elif ch in ")]}":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _parse_params(args_str: str):
    parts = _split_params(args_str)
    arity = 0
    has_var = False
    for p in parts:
        if p in ("*", "/"):
            continue
        if p.startswith("*"):
            has_var = True
            continue
        arity += 1
    return arity, has_var


_SIG_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(((?:[^()]|\([^()]*\))*)\)\s*->")


def _parse_real_signatures(text: str) -> Dict[str, Dict[str, Any]]:
    sigs: Dict[str, Dict[str, Any]] = {}
    for m in _SIG_PATTERN.finditer(text or ""):
        name = m.group(1)
        arity, has_var = _parse_params(m.group(2))
        sigs[name] = {"arity": arity, "var": has_var}
    return sigs


def _func_arity(node):
    args = node.args
    arity = len(args.args) + len(getattr(args, "posonlyargs", []) or []) + len(args.kwonlyargs)
    has_var = args.vararg is not None or args.kwarg is not None
    return (arity, has_var)


def _collect_raw(tree, seen_strings):
    functions: Dict[str, Any] = {}
    alias_map: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = _func_arity(node)
        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                alias_map[node.targets[0].id] = node.value.id
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
            if s not in seen_strings and 0 < len(s) < 100000:
                seen_strings.add(s)
                try:
                    sub_tree = ast.parse(s)
                except (SyntaxError, ValueError):
                    sub_tree = None
                if sub_tree is not None:
                    sub_functions, sub_aliases = _collect_raw(sub_tree, seen_strings)
                    functions.update(sub_functions)
                    alias_map.update(sub_aliases)
    return functions, alias_map


def _resolve_aliases(alias_map, functions):
    resolved = {}
    for name in alias_map:
        seen = set()
        cur = name
        while cur in alias_map and cur not in seen:
            seen.add(cur)
            cur = alias_map[cur]
        if cur in functions:
            resolved[name] = functions[cur]
    return resolved


def _collect_fake_functions(tree):
    functions, alias_map = _collect_raw(tree, set())
    functions.update(_resolve_aliases(alias_map, functions))
    return functions


def _validate_content(content: str, dependency_interfaces):
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        return {"category": "malformed_code", "message": f"syntax error: {exc}"}

    real_sigs: Dict[str, Dict[str, Any]] = {}
    for dep_iface in (dependency_interfaces or {}).values():
        real_sigs.update(_parse_real_signatures(dep_iface or ""))

    fakes = _collect_fake_functions(tree)
    mismatches = []
    for name, (arity, has_var) in fakes.items():
        if name not in real_sigs:
            continue
        real_arity = real_sigs[name]["arity"]
        real_var = real_sigs[name]["var"]
        if has_var or real_var:
            continue
        if arity != real_arity:
            mismatches.append(f"{name}: fake arity={arity}, real arity={real_arity}")

    if mismatches:
        return {"category": "fake_signature_mismatch", "message": "; ".join(mismatches)}
    return None


def _extract_content(text: Optional[str], nonce: str):
    if not text:
        return None, {"category": "missing_markers", "message": "model returned no text"}
    pattern = re.compile(
        r"-----BEGIN FILE " + re.escape(nonce) + r"-----\n(.*?)\n-----END FILE " + re.escape(nonce) + r"-----",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None, {"category": "missing_markers", "message": "no BEGIN/END FILE marker pair found"}
    return match.group(1), None


def _build_prompt(bundle: Any, nonce: str) -> str:
    component_id = _get(bundle, "component_id", "") or ""
    criterion_id = _get(bundle, "criterion_id", "") or ""
    covers = _get(bundle, "covers", "") or ""
    criterion_text = _get(bundle, "criterion_text", "") or ""
    requirement_text = _get(bundle, "requirement_text", "") or ""
    interface_text = _get(bundle, "interface", "") or ""
    glossary_text = _get(bundle, "glossary", "") or ""
    dependency_interfaces = _get(bundle, "dependency_interfaces", {}) or {}

    dep_sections = []
    for dep_id, dep_iface in dependency_interfaces.items():
        dep_sections.append(f"### Dependency `{dep_id}` — real interface contract\n\n{dep_iface}\n")
    dep_block = "\n".join(dep_sections) if dep_sections else "(This component has no dependencies.)"

    return f"""You are authoring a single Python test file for one acceptance criterion.
You have NO tool access and NO file access. Answer using only the
material in this prompt; you cannot read the target component's own
source code, and it has not been given to you.

## Target component

component_id: {component_id}

## Criterion under test

criterion_id: {criterion_id}
covers: {covers}

Given/When/Then text:
{criterion_text}

The covered requirement's own text:
{requirement_text}

## Target component's public interface contract

{interface_text}

## Glossary

{glossary_text}

## Dependency interfaces

Every dependency of the target component is listed below. Each entry is
that dependency's own real, documented, already-public interface
contract. If your test needs to fake a dependency's behavior, the fake
MUST match that dependency's real call signature and return shape
EXACTLY — never invent or simplify one.

Worked example: if a dependency's documented return type is a named-field
structure such as `ModelResponse {{ text, model, backend, model_call_error }}`,
a fake for it MUST construct and return an object/dict exposing ALL FOUR
fields — never just the one field your test happens to read, and never a
bare list/string/number instead.

{dep_block}

## How this corpus resolves dependencies at runtime (for the component
## under test ONLY — never for how your test imports the component
## under test itself)

Import the component under test normally, with a plain
`import <module_name>` — never a custom loader for the component under
test itself.

The component under test resolves ITS OWN dependencies dynamically, at
runtime, never via a static import: no dependency is statically
importable. A dependency named `some-dep-slug` is loaded from
`<repo_root>/gen/some-dep-slug/some_dep_slug.py` (flat module) or
`<repo_root>/gen/some-dep-slug/some_dep_slug/__init__.py` (package) —
`module_name` is always the slug with hyphens replaced by underscores,
never the literal string `"__init__"`. You can NEVER intercept a
dependency by name-based `sys.modules` injection or `mock.patch` —
neither one is seen by the real runtime loader.

To fake a dependency, write a fake module FILE under a fresh, temporary
`repo_root` directory, always in flat-module shape (every real loader
checks the flat shape first):

```
<temp_repo_root>/gen/some-dep-slug/some_dep_slug.py
```

Then pass that temporary `repo_root` into the component under test.

The one correctness-critical step, as a literal snippet — register the
loaded module in `sys.modules` BEFORE calling `exec_module`, never
after, never omitted. Skipping this breaks any dependency module that
defines a dataclass, because a dataclass's class body looks up
`sys.modules[cls.__module__]` while it executes:

```python
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(module_name, module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module   # MUST happen before exec_module
spec.loader.exec_module(module)
```

## Synthetic spec-corpus fixtures

If this criterion's test needs to construct synthetic spec files (a
fake `component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`,
or any other frontmatter-bearing document), every such document MUST
carry the frontmatter fields `SPEC_GUIDELINES.md` requires: `id`,
`title`, `status`, `owners` are always required, and `status` MUST be
exactly one of `draft`, `ratified`, or `deprecated`. Every
`requirements/` file needs a matching `acceptance/` file with a
`Covers:` tag, for every component your fixture constructs — not just
the target. A document with `status: ratified` MUST also set a
placeholder `last_ratified_commit`.

The OPPOSITE also holds: a unit file — `constraints.md`, or anything
under `requirements/`, `interface/`, or `acceptance/` — carries NO
frontmatter at all. Do not add frontmatter to those.

Any list-valued frontmatter field (`owners`, `depends_on`, `realizes`,
`uses_var`) in a synthetic fixture MUST use YAML flow style, e.g.
`owners: [alice]`, never YAML block style — this corpus's frontmatter
reader does not recognize block style as a list at all.

A synthetic fixture SHOULD default to `sealed: true` with a short, fake
`source_path` not under `gen/`, unless this criterion specifically
concerns `realizes`/capability linkage — `sealed: true` exempts a
component from `realizes` and the whole capability-linkage machinery.
Only supply a resolvable `P-<id>` in `realizes` if the criterion
genuinely needs `realizes`-driven behavior.

If this criterion depends on a precondition the target checks against
`spec-linter`, your test MUST call `lint()` against the fixture first
and assert there are zero hard-fail findings before exercising the real
behavior under test — this is a MUST, not left to judgment. Use this
exact call, literally, with `paths` positionally first as `None`:

```python
findings = lint(None, repo_root)
assert not any(f.severity == "hard-fail" for f in findings)
```

(Use dual dict-or-attribute access on each finding if its shape is not
certain.)

Your test MUST NEVER `import yaml` or any other third-party package
that is not already part of the Python standard library — write and
parse any frontmatter as plain text instead.

## Reading values the target returns

Every field you read from a value the TARGET COMPONENT ITSELF returns
(not only a faked dependency's data) MUST use dual dict-or-attribute
access, since this corpus's components may return either a dict or an
object in a given round:

```python
value = result["field"] if isinstance(result, dict) else result.field
```

Never assume one shape only.

## Confirming a fake ran

Never assert that a fake was used by reaching into `sys.modules` under
a guessed key — real loaders key dynamically (often qualified by
`repo_root` or a hash), so any guess is unreliable. Instead, have the
fake itself record that it was invoked (e.g. append to a module-level
list, or write a marker file), and assert against that record.

## Output format

Respond with ONLY the test file's content, wrapped EXACTLY as follows,
with no fence, no narration, no preamble or postamble outside the
markers:

-----BEGIN FILE {nonce}-----
<the complete, exact test file content, verbatim>
-----END FILE {nonce}-----"""


def author_test(
    bundle: Any,
    model: str,
    seed: int = 0,
    *,
    repo_root: Optional[Path] = None,
    llm_backend=None,
) -> TestAuthoringResult:
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
    component_id = _get(bundle, "component_id")
    criterion_id = _get(bundle, "criterion_id")
    dependency_interfaces = _get(bundle, "dependency_interfaces", {}) or {}

    cache_manager = _load_dependency("cache-manager", "cache_manager", repo_root)
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=_criterion_content_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(seed),
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = _get(cached, "payload", {}) or {}
        file_payload = _get(payload, "file", {}) or {}
        path = _get(file_payload, "path")
        content = _get(file_payload, "content")
        _write_file(repo_root, path, content)
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=True,
            file=FileOutput(path=path, content=content),
            model_call_error=None,
        )

    nonce = secrets.token_hex(16)
    prompt = _build_prompt(bundle, nonce)
    llm_endpoint = _load_dependency("llm-endpoint", "llm_endpoint", repo_root)
    response = llm_endpoint.complete(prompt, model, backend=llm_backend)

    error = _get(response, "model_call_error")
    if error:
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

    text = _get(response, "text")
    content, extract_error = _extract_content(text, nonce)
    if extract_error:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=extract_error,
        )

    validation_error = _validate_content(content, dependency_interfaces)
    if validation_error:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=validation_error,
        )

    path = _output_path(component_id, criterion_id)
    _write_file(repo_root, path, content)

    payload = {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "model": model,
        "file": {"path": path, "content": content},
        "seed": seed,
        "prompt_version": PROMPT_VERSION,
    }
    cache_manager.put(
        cache_key,
        cache_manager.CachedResult(gate_type="generated_test", payload=payload, stored_at=cache_manager.now_iso()),
        repo_root=repo_root,
    )

    return TestAuthoringResult(
        component_id=component_id,
        criterion_id=criterion_id,
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        file=FileOutput(path=path, content=content),
        model_call_error=None,
    )


def _to_jsonable(result: TestAuthoringResult) -> dict:
    return asdict(result) if is_dataclass(result) else dict(result)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="author-test")
    parser.add_argument("component_id")
    parser.add_argument("criterion_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", choices=["json", "text"], default="text")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    repo_root = Path(args.repo_root) if args.repo_root else Path.cwd()

    try:
        assembler = _load_dependency("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
        bundle = assembler.assemble_criterion(args.component_id, args.criterion_id, repo_root)
    except Exception as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    result = author_test(bundle, args.model, args.seed, repo_root=repo_root)
    error = _get(result, "model_call_error")

    if args.format == "json":
        print(json.dumps(_to_jsonable(result)))
    else:
        if error:
            print(f"model call error: {error}")
        else:
            file_out = _get(result, "file")
            print(f"wrote {_get(file_out, 'path')}")

    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())