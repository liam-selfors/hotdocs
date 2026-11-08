"""Authors generated-test code for one acceptance criterion from spec prose alone.

See specs/components/test-author/ for the full contract (R-AUTHOR-001..026).
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import secrets
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


PROMPT_VERSION = "v1"
GATE_VERSION = "generated_test@1.0.0"


# ---------------------------------------------------------------------------
# Dual dict-or-attribute access (this corpus's duck-typing convention, D94)
# ---------------------------------------------------------------------------


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


# ---------------------------------------------------------------------------
# Dynamic dependency loading
#
# Resolution order: repo_root/gen/<dep-slug>/<module_name>.py (flat), then
# repo_root/gen/<dep-slug>/<module_name>/__init__.py (package); only if
# neither exists under repo_root, fall back to the same two shapes under
# the tool's own `gen/` root (the parent of the nearest directory named
# `gen` above this module's own __file__). repo_root always wins when it
# has the directory.
# ---------------------------------------------------------------------------


def _tool_gen_root() -> Optional[Path]:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent
    return None


def _exec_module_from_file(module_name: str, file_path: Path, package_dir: Optional[Path] = None):
    spec = importlib.util.spec_from_file_location(
        module_name,
        file_path,
        submodule_search_locations=[str(package_dir)] if package_dir else None,
    )
    module = importlib.util.module_from_spec(spec)
    # Must register in sys.modules BEFORE exec_module: dataclasses look up
    # sys.modules[cls.__module__] while their class body executes.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_dependency(repo_root: Path, dep_slug: str, module_name: str):
    repo_root = Path(repo_root) if repo_root else Path.cwd()
    bases = [repo_root / "gen" / dep_slug]
    tool_gen = _tool_gen_root()
    if tool_gen is not None:
        tool_base = tool_gen / dep_slug
        if tool_base not in bases:
            bases.append(tool_base)

    for base in bases:
        flat = base / f"{module_name}.py"
        if flat.is_file():
            return _exec_module_from_file(module_name, flat)
        pkg_init = base / module_name / "__init__.py"
        if pkg_init.is_file():
            return _exec_module_from_file(module_name, pkg_init, package_dir=base / module_name)

    raise ImportError(
        f"could not locate dependency module '{module_name}' for '{dep_slug}' under any of {bases!r}"
    )


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class TestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: Optional[dict] = None
    model_call_error: Optional[dict] = None


# ---------------------------------------------------------------------------
# Prompt construction (R-AUTHOR-009..015, 019..026)
# ---------------------------------------------------------------------------


def _target_module_name(component_id: str) -> str:
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    return slug.replace("-", "_")


def _import_instruction(component_id: str, module_names: list) -> str:
    if module_names:
        lines = "\n".join(f"import {name}" for name in module_names)
        return (
            "This criterion's bundle names the following module(s) under test "
            "(a capability scenario names the realizing components' modules here, "
            "in place of a single derived name). Import each exactly as written, "
            "in this order:\n"
            f"{lines}\n"
            "Do not derive or guess any other import statement for the component under test."
        )
    module_name = _target_module_name(component_id)
    return (
        f"The component under test's own module is `{module_name}` "
        f"(its slug with every hyphen replaced by an underscore). "
        f"Import it with the exact statement `import {module_name}`. "
        f"Never infer this name from a function name or from the component id itself "
        f"(`comp_{module_name}` would be wrong). The real module may be laid out as "
        f"`{module_name}.py` or a `{module_name}/` package — the import statement is "
        f"identical either way."
    )


def _dependency_resolution_instruction() -> str:
    return (
        "## How the component under test resolves ITS OWN dependencies\n\n"
        "The component under test itself needs no custom loader: a plain "
        "`import <module_name>` is how you import the component under test "
        "(see the instruction above for its exact module name). That statement "
        "is the only thing you, the test author, ever write to reach the "
        "component under test.\n\n"
        "However, no dependency OF the component under test is statically "
        "importable anywhere in this corpus. Resolution of the component's own "
        "dependencies is dynamic, at runtime, from "
        "`<repo_root>/gen/<dependency-slug>/<module_name>.py` (flat) or "
        "`<repo_root>/gen/<dependency-slug>/<module_name>/__init__.py` (package), "
        "else the tool's own copy of the same path — so omitting a dependency "
        "from a fake `repo_root` never makes that dependency appear missing to "
        "the real loader; it is never interceptable by name-based `sys.modules` "
        "injection or `mock.patch`.\n\n"
        "To fake a dependency's behavior for a test, write a fake module FILE "
        "under a fresh temporary `repo_root` you construct — always in flat-module "
        "shape (`<module_name>.py`, never a package `__init__.py`): every real "
        "loader in this corpus checks the flat form first. `module_name` here is "
        "the dependency's slug with hyphens replaced by underscores, and is never "
        "literally `\"__init__\"`.\n\n"
        "If your test needs to load that fake module file itself (e.g. to assert "
        "something about it directly), use this exact pattern — registering the "
        "module in `sys.modules` BEFORE calling `exec_module`, which any dependency "
        "defining a dataclass requires:\n\n"
        "```python\n"
        "import importlib.util\n"
        "spec = importlib.util.spec_from_file_location(module_name, module_path)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules[module_name] = module  # register BEFORE exec_module\n"
        "spec.loader.exec_module(module)\n"
        "```\n"
    )


def _dependency_interfaces_section(dependency_interfaces: dict) -> str:
    if not dependency_interfaces:
        return (
            "## Dependencies\n\nThis target has no `dependency_interfaces` entries in its bundle.\n"
        )
    parts = ["## Dependencies\n"]
    parts.append(
        "Below is each dependency's own `interface/` content — its real, documented, "
        "public contract. Any fake you write for a dependency's behavior MUST match "
        "that dependency's real documented call signature and return shape exactly — "
        "never invented, never simplified, and never read from the target's own "
        "implementation (which you do not have, and must not assume anything about).\n\n"
        "Worked example: if a dependency's documented return type is named with fields, "
        "e.g. `Foo(a: str, b: int) -> None`, your fake MUST return something exposing "
        "EVERY field (`{\"a\": ..., \"b\": ...}` or an object with both `a` and `b` "
        "attributes) — never a bare string, list, or number, even if the test under "
        "construction only ever reads `a`.\n"
    )
    for dep_id, iface_text in dependency_interfaces.items():
        parts.append(f"### {dep_id}\n\n{iface_text}\n")
    return "\n".join(parts)


def _fixture_instruction() -> str:
    return (
        "## Synthetic fixtures\n\n"
        "If this criterion requires constructing a synthetic spec-corpus fixture "
        "(a fake `component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`, "
        "or similar), it MUST carry the frontmatter `SPEC_GUIDELINES.md` requires on "
        "every such document: `id`, `title`, `status`, `owners` always present, and "
        "`status` exactly one of `draft`/`ratified`/`deprecated`. Every `requirements/` "
        "file in such a fixture needs a matching `acceptance/` file with a `Covers:` "
        "tag. `status: ratified` also sets a placeholder `last_ratified_commit`. "
        "A unit file — `constraints.md`, or anything under `requirements/`, "
        "`interface/`, or `acceptance/` — carries NO frontmatter at all. Never "
        "`import yaml` or any other not-already-installed third-party package in the "
        "test; write and parse any frontmatter as plain text.\n\n"
        "Any list-valued frontmatter field (`owners`, `depends_on`, `realizes`, "
        "`uses_var`) in a synthetic fixture MUST use YAML flow style, e.g. "
        "`owners: [alice, bob]` — never block style (`owners:\\n  - alice`); this "
        "corpus's frontmatter reader does not recognize block style as a list.\n\n"
        "A synthetic fixture SHOULD default to `sealed: true` with a short, fake "
        "`source_path` not under `gen/` unless this criterion specifically concerns "
        "`realizes`/capability linkage — sealed exempts the fixture from `realizes` "
        "and the capability machinery. Only when the criterion genuinely needs "
        "`realizes`-driven behavior should the fixture instead supply a resolvable "
        "`P-<id>`.\n\n"
        "If this criterion depends on a precondition the target checks against "
        "`spec-linter`, the test MUST call `lint()` against the fixture first and "
        "assert zero hard-fail findings before exercising the real behavior under "
        "test, using exactly this call shape (positional `paths=None` first, never "
        "a single positional argument):\n\n"
        "```python\n"
        "lint(None, repo_root)\n"
        "```\n"
    )


def _misc_instructions() -> str:
    return (
        "## Other rules for the test you write\n\n"
        "- Every field you read from a value the component under test itself "
        "returns (not only a faked dependency's data) MUST use dual dict-or-"
        "attribute access — e.g. `value.get(\"x\") if isinstance(value, dict) else "
        "getattr(value, \"x\", None)` — never a bare `.attr` access alone, since any "
        "component in this corpus may return either shape in a given round.\n"
        "- NEVER assert that a fake was used by reaching into `sys.modules` under a "
        "guessed key. Real loaders key `sys.modules` dynamically (often qualified by "
        "`repo_root` or a content hash), so any guessed key is unreliable. To confirm "
        "a fake ran, have the fake's own code append an invocation record to a FILE "
        "under a path your test controls and constructs (e.g. a temp-dir log file) — "
        "never an in-process, module-level list, since the test cannot reliably "
        "re-locate the module object that wrote to it either.\n"
        "- If asserting that a wall-clock \"own write time\" field falls within a "
        "`[before, after]` window, truncate `before`/`after` to the same precision "
        "the field's own documented format carries (e.g. to whole seconds for a "
        "`%Y-%m-%dT%H:%M:%SZ`-formatted example with no fractional digits) — never "
        "compare a truncated-on-write timestamp against microsecond-precision "
        "bounds directly.\n"
        "- Write plain, runnable Python test code only — no narration, no markdown "
        "fences, no commentary outside the file content itself.\n"
    )


def _build_prompt(
    component_id: str,
    criterion_id: str,
    covers: Optional[str],
    criterion_text: Optional[str],
    requirement_text: Optional[str],
    interface_text: Optional[str],
    glossary_text: Optional[str],
    dependency_interfaces: dict,
    module_names: list,
    nonce: str,
) -> str:
    sections = []
    sections.append(
        "You are authoring a single Python test file for one acceptance criterion "
        "of a component in a spec-driven pipeline. You have NO tool access and NO "
        "file access of any kind. You must answer using ONLY the information given "
        "to you below — the criterion's own bundle — and nothing else. In "
        "particular, you have NOT been given, and must never assume anything about, "
        "the component under test's actual `gen/<component>/` source code — only "
        "its `interface/` contract below. Write the test against that contract, "
        "never against an implementation you do not have."
    )
    sections.append(f"## Component under test\n\n`{component_id}`")
    sections.append(f"## Criterion\n\n`{criterion_id}` — covers `{covers}`\n\n{criterion_text or ''}")
    sections.append(f"## The covered requirement's own text\n\n{requirement_text or ''}")
    sections.append(f"## Target component's interface/ contract\n\n{interface_text or ''}")
    sections.append(_import_instruction(component_id, module_names))
    sections.append(_dependency_resolution_instruction())
    sections.append(_dependency_interfaces_section(dependency_interfaces))
    sections.append(_fixture_instruction())
    sections.append(_misc_instructions())
    sections.append(f"## Glossary\n\n{glossary_text or ''}")
    sections.append(
        "## Output format\n\n"
        "Respond with exactly one test file, wrapped EXACTLY as:\n\n"
        f"-----BEGIN FILE {nonce}-----\n"
        "<the complete, exact test file content, verbatim>\n"
        f"-----END FILE {nonce}-----\n\n"
        "Nothing may appear before the BEGIN marker or after the END marker — no "
        "narration, no preamble, no postamble, no surrounding code fence. Everything "
        "strictly between the markers is taken as the file content verbatim."
    )
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Extraction (R-AUTHOR-009)
# ---------------------------------------------------------------------------


def _extract_file(text: Optional[str], nonce: str) -> Optional[str]:
    if text is None:
        return None
    pattern = re.compile(
        r"-----BEGIN FILE " + re.escape(nonce) + r"-----\r?\n(.*?)\r?\n-----END FILE "
        + re.escape(nonce) + r"-----",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1)


# ---------------------------------------------------------------------------
# Static validation (R-AUTHOR-020)
# ---------------------------------------------------------------------------


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _split_top_level(s: str) -> list:
    parts = []
    depth = 0
    current = ""
    for c in s:
        if c in "([{":
            depth += 1
            current += c
        elif c in ")]}":
            depth -= 1
            current += c
        elif c == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += c
    if current.strip():
        parts.append(current)
    return parts


def _count_params(params_str: str):
    count = 0
    variadic = False
    for part in _split_top_level(params_str):
        part = part.strip()
        if not part or part == "*":
            continue
        if part.startswith("**") or part.startswith("*"):
            variadic = True
            continue
        count += 1
    return count, variadic


def _find_signatures(text: str) -> list:
    """Best-effort scan for `name(args) -> ReturnType` signatures in interface prose."""
    results = []
    i = 0
    n = len(text)
    while i < n:
        m = _IDENT_RE.match(text, i)
        if not m:
            i += 1
            continue
        name = m.group(0)
        j = m.end()
        if j < n and text[j] == "(":
            depth = 0
            k = j
            closed = False
            while k < n:
                c = text[k]
                if c in "([{":
                    depth += 1
                elif c in ")]}":
                    depth -= 1
                    if depth == 0 and c == ")":
                        closed = True
                        break
                k += 1
            if not closed:
                i = j + 1
                continue
            params_str = text[j + 1:k]
            rest = text[k + 1:k + 30]
            if rest.lstrip().startswith("->"):
                count, variadic = _count_params(params_str)
                results.append((name, count, variadic))
            i = k + 1
        else:
            i = j
    return results


def _funcdef_arity(node: ast.FunctionDef):
    args = node.args
    count = len(getattr(args, "posonlyargs", []) or []) + len(args.args) + len(args.kwonlyargs)
    variadic = args.vararg is not None or args.kwarg is not None
    return count, variadic


def _validate_fake_arities(test_code: str, dependency_interfaces: dict) -> Optional[dict]:
    dep_sigs = {}
    for iface_text in (dependency_interfaces or {}).values():
        if not iface_text:
            continue
        for name, arity, variadic in _find_signatures(iface_text):
            dep_sigs.setdefault(name, []).append((arity, variadic))
    if not dep_sigs:
        return None

    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        return None  # syntax errors are reported separately, before this check runs

    fake_arities = {}
    aliases = {}

    def scan_body(body):
        for node in body:
            if isinstance(node, ast.FunctionDef):
                fake_arities[node.name] = _funcdef_arity(node)
            elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target_name = node.targets[0].id
                value = node.value
                if isinstance(value, ast.Name):
                    aliases[target_name] = value.id
                elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                    try:
                        sub_tree = ast.parse(value.value)
                        scan_body(sub_tree.body)
                    except SyntaxError:
                        pass

    scan_body(tree.body)

    for alias_name, target_name in aliases.items():
        if alias_name not in fake_arities and target_name in fake_arities:
            fake_arities[alias_name] = fake_arities[target_name]

    for name, (count, variadic) in fake_arities.items():
        if variadic or name not in dep_sigs:
            continue
        candidates = dep_sigs[name]
        if any(dep_variadic or dep_arity == count for dep_arity, dep_variadic in candidates):
            continue
        expected = [a for a, _ in candidates]
        return {
            "category": "fake_signature_mismatch",
            "message": (
                f"fake '{name}' defined with {count} parameter(s); "
                f"dependency interface declares arity {expected}"
            ),
            "function": name,
            "actual_arity": count,
            "expected_arity": expected,
        }
    return None


# ---------------------------------------------------------------------------
# Output path (R-AUTHOR-006, D63)
# ---------------------------------------------------------------------------


def _slug(component_id: str) -> str:
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _criterion_filename(criterion_id: str) -> str:
    return f"test_{criterion_id.lower().replace('-', '_')}.py"


def _output_path(component_id: str, criterion_id: str) -> str:
    return f"verification/{_slug(component_id)}/generated-test/{_criterion_filename(criterion_id)}"


def _write_file(repo_root: Path, file_info: Any) -> None:
    if not file_info:
        return
    path = _get(file_info, "path")
    content = _get(file_info, "content")
    if path is None or content is None:
        return
    full_path = Path(repo_root) / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def author_test(
    bundle: Any,
    model: str,
    seed: int = 0,
    *,
    repo_root: Optional[Path] = None,
    llm_backend=None,
) -> TestAuthoringResult:
    repo_root = Path(repo_root) if repo_root else Path.cwd()

    component_id = _get(bundle, "component_id")
    criterion_id = _get(bundle, "criterion_id")
    covers = _get(bundle, "covers")
    criterion_text = _get(bundle, "criterion_text")
    requirement_text = _get(bundle, "requirement_text")
    interface_text = _get(bundle, "interface")
    glossary_text = _get(bundle, "glossary")
    dependency_interfaces = _get(bundle, "dependency_interfaces", {}) or {}
    module_names = _get(bundle, "module_names", []) or []

    cache_manager = _load_dependency(repo_root, "cache-manager", "cache_manager")
    llm_endpoint = _load_dependency(repo_root, "llm-endpoint", "llm_endpoint")

    criterion_content = json.dumps(
        {
            "component_id": component_id,
            "criterion_id": criterion_id,
            "covers": covers,
            "criterion_text": criterion_text,
            "requirement_text": requirement_text,
            "interface": interface_text,
            "glossary": glossary_text,
            "dependency_interfaces": dependency_interfaces,
            "module_names": module_names,
        },
        sort_keys=True,
        default=str,
    )
    criterion_hash = "sha256:" + hashlib.sha256(criterion_content.encode("utf-8")).hexdigest()

    gate_inputs_content = json.dumps({"seed": seed, "prompt_version": PROMPT_VERSION}, sort_keys=True)
    gate_inputs_hash = "sha256:" + hashlib.sha256(gate_inputs_content.encode("utf-8")).hexdigest()

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=criterion_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = _get(cached, "payload", {}) or {}
        file_info = _get(payload, "file")
        _write_file(repo_root, file_info)
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
    prompt = _build_prompt(
        component_id,
        criterion_id,
        covers,
        criterion_text,
        requirement_text,
        interface_text,
        glossary_text,
        dependency_interfaces,
        module_names,
        nonce,
    )

    response = llm_endpoint.complete(prompt, model, backend=llm_backend)
    resp_error = _get(response, "model_call_error")
    if resp_error is not None:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=resp_error,
        )

    resp_text = _get(response, "text")
    extracted = _extract_file(resp_text, nonce)
    if extracted is None:
        error = {
            "category": "no_markers",
            "message": "no matching BEGIN/END FILE marker pair found in model response",
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

    try:
        ast.parse(extracted)
    except SyntaxError as exc:
        error = {
            "category": "malformed_code",
            "message": f"authored test failed to parse as Python: {exc}",
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

    arity_error = _validate_fake_arities(extracted, dependency_interfaces)
    if arity_error is not None:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=arity_error,
        )

    file_info = {"path": _output_path(component_id, criterion_id), "content": extracted}

    cached_result = cache_manager.CachedResult(
        gate_type="generated_test",
        payload={
            "component_id": component_id,
            "criterion_id": criterion_id,
            "model": model,
            "file": file_info,
        },
        stored_at=cache_manager.now_iso(),
    )
    cache_manager.put(cache_key, cached_result, repo_root=repo_root)

    _write_file(repo_root, file_info)

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


_USAGE = (
    "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)


def _result_to_dict(result: Any) -> dict:
    if isinstance(result, dict):
        return result
    return asdict(result)


def main(argv: Optional[list] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if not argv or argv[0] != "author-test":
        print(_USAGE, file=sys.stderr)
        return 2

    rest = argv[1:]
    positional = []
    model = None
    seed = 0
    repo_root = Path.cwd()
    fmt = "text"

    for arg in rest:
        if arg.startswith("--model="):
            model = arg.split("=", 1)[1]
        elif arg.startswith("--seed="):
            try:
                seed = int(arg.split("=", 1)[1])
            except ValueError:
                print(_USAGE, file=sys.stderr)
                return 2
        elif arg.startswith("--repo-root="):
            repo_root = Path(arg.split("=", 1)[1])
        elif arg.startswith("--format="):
            fmt = arg.split("=", 1)[1]
        elif arg.startswith("--"):
            print(_USAGE, file=sys.stderr)
            return 2
        else:
            positional.append(arg)

    if len(positional) != 2 or model is None or fmt not in ("json", "text"):
        print(_USAGE, file=sys.stderr)
        return 2

    component_id, criterion_id = positional

    try:
        assembler = _load_dependency(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
        bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    except Exception as exc:
        print(f"usage error: could not assemble criterion bundle: {exc}", file=sys.stderr)
        return 2

    result = author_test(bundle, model, seed, repo_root=repo_root)

    error = _get(result, "model_call_error")
    if fmt == "json":
        print(json.dumps(_result_to_dict(result)))
    else:
        if error:
            print(f"model-call error: {error}")
        else:
            file_info = _get(result, "file")
            print(
                f"wrote {_get(file_info, 'path')} "
                f"(cache_hit={_get(result, 'cache_hit')})"
            )

    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())