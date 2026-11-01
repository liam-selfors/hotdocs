import ast
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from pathlib import Path

PROMPT_VERSION = "v1"
GATE_VERSION = "generated_test@1.0.0"

_MISSING = object()

_SIG_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\(([^)]*)\)\s*->\s*([^\n`]+)")


def _dual_get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _slug(component_id):
    if not component_id:
        return ""
    if component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _load_dependency(repo_root, slug, module_name):
    repo_root = Path(repo_root)
    dep_dir = repo_root / "gen" / slug
    flat_path = dep_dir / f"{module_name}.py"
    pkg_init = dep_dir / module_name / "__init__.py"

    if flat_path.exists():
        path = flat_path
        submodule_locations = None
    elif pkg_init.exists():
        path = pkg_init
        submodule_locations = [str(pkg_init.parent)]
    else:
        raise ModuleNotFoundError(
            f"dependency module '{module_name}' not found under {dep_dir}"
        )

    qualifier = hashlib.sha256(str(repo_root.resolve()).encode("utf-8")).hexdigest()[:12]
    unique_name = f"_test_author_dep_{module_name}_{qualifier}"

    spec = importlib.util.spec_from_file_location(
        unique_name, path, submodule_search_locations=submodule_locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def _criterion_hash(bundle):
    dependency_interfaces = _dual_get(bundle, "dependency_interfaces") or {}
    if not isinstance(dependency_interfaces, dict):
        dependency_interfaces = {}
    payload = {
        "component_id": _dual_get(bundle, "component_id"),
        "criterion_id": _dual_get(bundle, "criterion_id"),
        "covers": _dual_get(bundle, "covers"),
        "criterion_text": _dual_get(bundle, "criterion_text"),
        "requirement_text": _dual_get(bundle, "requirement_text"),
        "interface": _dual_get(bundle, "interface"),
        "glossary": _dual_get(bundle, "glossary"),
        "dependency_interfaces": dependency_interfaces,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _gate_inputs_hash(seed, prompt_version):
    encoded = json.dumps(
        {"seed": seed, "prompt_version": prompt_version}, sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _is_cache_hit(cached, cache_manager_mod):
    if isinstance(cached, cache_manager_mod.Miss):
        return False
    payload = _dual_get(cached, "payload", _MISSING)
    return payload is not _MISSING


def _result(component_id, criterion_id, model, seed, cache_hit, file, model_call_error):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "model": model,
        "seed": seed,
        "prompt_version": PROMPT_VERSION,
        "cache_hit": cache_hit,
        "file": file,
        "model_call_error": model_call_error,
    }


def _extract_file(text, nonce):
    if not text:
        return None
    pattern = re.compile(
        r"-----BEGIN FILE "
        + re.escape(nonce)
        + r"-----\n(.*?)\n-----END FILE "
        + re.escape(nonce)
        + r"-----",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1)


def _split_top_level(s):
    parts = []
    depth = 0
    current = ""
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current)
    return parts


def _parse_param_count(params_str):
    params_str = params_str.strip()
    if not params_str:
        return 0, False
    count = 0
    flexible = False
    for part in _split_top_level(params_str):
        part = part.strip()
        if not part or part == "*" or part == "/":
            continue
        if part.startswith("**") or part.startswith("*"):
            flexible = True
            continue
        count += 1
    return count, flexible


def _collect_dependency_signatures(dependency_interfaces):
    registry = {}
    for _dep_id, text in (dependency_interfaces or {}).items():
        if not isinstance(text, str):
            continue
        for match in _SIG_RE.finditer(text):
            name, params, _ret = match.groups()
            count, flexible = _parse_param_count(params)
            registry.setdefault(name, []).append((count, flexible))
    return registry


def _func_arity(args):
    count = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    flexible = args.vararg is not None or args.kwarg is not None
    return count, flexible


def _collect_fake_arities(tree):
    arities = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            arities[node.name] = _func_arity(node.args)

    aliases = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
        ):
            aliases[node.targets[0].id] = node.value.id
    for alias, target in aliases.items():
        if target in arities:
            arities.setdefault(alias, arities[target])

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                sub_tree = ast.parse(node.value)
            except Exception:
                continue
            for sub in sub_tree.body:
                if isinstance(sub, ast.FunctionDef):
                    arities.setdefault(sub.name, _func_arity(sub.args))

    return arities


def _check_fake_arity(code, dependency_interfaces):
    dep_sigs = _collect_dependency_signatures(dependency_interfaces)
    if not dep_sigs:
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    fake_arities = _collect_fake_arities(tree)
    for name, (count, flexible) in fake_arities.items():
        if name not in dep_sigs or flexible:
            continue
        candidates = dep_sigs[name]
        if any(dep_flexible or dep_count == count for dep_count, dep_flexible in candidates):
            continue
        dep_desc = ", ".join(
            "variadic" if dep_flexible else str(dep_count)
            for dep_count, dep_flexible in candidates
        )
        return {
            "category": "fake_signature_mismatch",
            "message": (
                f"fake '{name}' defines arity {count}, but the dependency's "
                f"documented signature(s) for '{name}' require arity [{dep_desc}]"
            ),
        }
    return None


def _build_prompt(bundle, nonce, dependency_interfaces):
    component_id = _dual_get(bundle, "component_id", "")
    criterion_id = _dual_get(bundle, "criterion_id", "")
    covers = _dual_get(bundle, "covers", "")
    criterion_text = _dual_get(bundle, "criterion_text", "")
    requirement_text = _dual_get(bundle, "requirement_text", "")
    interface_text = _dual_get(bundle, "interface", "")
    glossary_text = _dual_get(bundle, "glossary", "")

    dep_sections = []
    for dep_id, dep_interface in (dependency_interfaces or {}).items():
        dep_sections.append(f"### Dependency `{dep_id}` interface contract\n\n{dep_interface}")
    dep_block = "\n\n".join(dep_sections) if dep_sections else "(this component has no dependencies)"

    return f"""You are authoring an automated test for one acceptance criterion of
component `{component_id}`. You have NO tool access and NO file access.
Answer using only the material given below in this prompt.

## Criterion under test

Criterion id: {criterion_id}
Covers requirement: {covers}

Criterion text (Given/When/Then):
{criterion_text}

Covered requirement's own text:
{requirement_text}

## Target component's public interface contract

This is the ONLY authoritative description of the target component's
behavior you may rely on. You have NOT been given, and MUST NOT assume
anything about, the target component's actual `gen/<component>/` source
code. Write the test strictly against this contract.

{interface_text}

## Dependency interface contracts

If the test needs to fake a dependency's behavior, each fake MUST match
that dependency's real, documented call signature and return shape
below EXACTLY -- never invent or simplify a signature or a return
shape. Worked example: if a dependency's documented return type has
named fields (e.g. a type with fields `text`, `model`, `backend`,
`model_call_error`), your fake's return value MUST expose every one of
those fields, even if this particular test only reads one of them --
never return a bare list, string, or number instead.

{dep_block}

## Glossary

{glossary_text}

## How the component under test resolves ITS OWN dependencies (read carefully)

This corpus's components are not a normal installed Python package. No
dependency is statically importable by the component under test. The
component under test resolves each of its own dependencies dynamically,
at runtime, from a `repo_root` it is given, by loading:

  `<repo_root>/gen/<dependency-slug>/<module_name>.py`           (flat module), or
  `<repo_root>/gen/<dependency-slug>/<module_name>/__init__.py`  (package)

`<module_name>` is the dependency's slug with every hyphen replaced by
an underscore (never the literal string `"__init__"`).

This resolution is NEVER interceptable by a name-based `sys.modules`
injection or by `mock.patch` from the test's side -- the loader keys
the module it loads under whatever name it chooses internally, not
under the dependency's plain module name, so patching
`sys.modules["some_dependency"]` or `mock.patch("some_dependency.fn")`
has no effect on what the component under test actually calls.

To fake a dependency for this test, create a fresh, temporary
`repo_root` directory for the test (e.g. via `tempfile.mkdtemp()` or
`tmp_path`), and under it write the fake as a FLAT module file at
`<temp_repo_root>/gen/<dependency-slug>/<module_name>.py` -- always
flat-module shape for a synthetic fake, never a package, because every
real loader checks the flat shape first. Then call the component under
test's own function, passing that temporary directory as its
`repo_root` argument.

This dynamic-loading convention applies ONLY to how the component
under test resolves its OWN dependencies internally. It does NOT apply
to how this test file itself imports the component under test -- the
test imports the component under test with a plain, ordinary
`import <module_name>` statement (the target component's own module is
already importable in the test environment), never a custom loader.

If your test itself needs to dynamically load any module from a file
path (which should only ever be a dependency fake you load back for
inspection, never the component under test), the one correctness-
critical step is this literal pattern -- register the module in
`sys.modules` BEFORE calling `exec_module`, never after:

```python
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(module_name, module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module  # MUST happen before exec_module
spec.loader.exec_module(module)
```

Skipping the `sys.modules` registration step, or doing it after
`exec_module`, crashes on any loaded module that defines a dataclass,
because a dataclass's class body resolves `sys.modules[cls.__module__]`
while the class body itself is executing.

## Building a synthetic fixture, if this criterion needs one

If this criterion needs a synthetic fixture component (a fake
`component.md`, `requirements/`, `interface/`, `acceptance/`, or
`specs/vars/VAR-*.md`, or `specs/decisions/D<N>.md` tree on disk):

- Every frontmatter-bearing document in that fixture (`component.md`,
  `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) MUST carry the
  frontmatter fields `id`, `title`, `status`, `owners`. `status` MUST
  be exactly one of `draft`, `ratified`, or `deprecated`. If `status`
  is `ratified`, also set a placeholder `last_ratified_commit` field.
- The opposite also holds: a unit file (`constraints.md`, or anything
  under `requirements/`, `interface/`, `acceptance/`) carries NO
  frontmatter at all.
- Every `requirements/` file in the fixture needs a matching
  `acceptance/` file with a `Covers:` tag pointing back to it -- for
  every fixture component you create, not only the target.
- Any list-valued frontmatter field (`owners`, `depends_on`,
  `realizes`, `uses_var`) MUST use YAML flow style, e.g. `[a, b]` --
  never block style (a `-`-per-line list). This corpus's frontmatter
  reader does not recognize block-style lists at all.
- Default every synthetic fixture component to `sealed: true` with a
  short, fake `source_path` that is NOT under `gen/` -- this exempts it
  from `realizes` and the whole capability-linkage machinery. Only
  supply a resolvable `realizes: [P-<id>]` if this specific criterion
  genuinely concerns `realizes`/capability linkage.
- Write and parse any frontmatter as plain text (e.g. simple line
  splitting/string matching). NEVER `import yaml` or any other
  not-already-installed third-party package in the test.
- If this criterion depends on a precondition the target checks via
  `spec-linter`, call `lint()` against the fixture FIRST and assert
  zero hard-fail findings before exercising the real behavior under
  test. Use exactly this call shape (positional `paths` first, as
  `None`, then `repo_root`):

```python
findings = lint(None, repo_root)
```

## Reading values the target component returns

Every field you read from a value the target component itself
returns (not only from a dependency fake's data) MUST use dual
dict-or-attribute access -- e.g. a small helper that tries `obj[key]`
if `obj` is a dict, else `getattr(obj, key)` -- never a bare `.attr`
access alone. Any component in this corpus may legitimately return
either a dict or an object with attributes in a given call.

## Confirming a fake was actually invoked

NEVER assert that a fake was used by reaching into `sys.modules` under
a guessed key -- real loaders key dynamically (often qualified by
`repo_root` or a content hash), so any guessed key is unreliable and
may not match. To confirm a fake ran, have the fake's own code APPEND
an invocation record to a FILE at a path the test controls, and have
the test read that file afterward -- never an in-process, module-level
list, since the test cannot reliably re-locate the module object that
would hold it.

## Comparing a recorded timestamp against a time window

If this test asserts that some wall-clock "own write time" field falls
within a `[before, after]` window, truncate `before` and `after` to
the SAME precision the field's own documented format carries (e.g.
whole seconds for a `%Y-%m-%dT%H:%M:%SZ`-style timestamp with no
fractional digits) before comparing -- never compare a value that was
truncated on write against microsecond-precision bounds directly.

## Output format (read carefully -- this is how your answer is extracted)

You have no tool or file access. Produce exactly one test file's
content, and wrap it EXACTLY as follows, with no other text before,
between, or after the markers besides the file content itself:

-----BEGIN FILE {nonce}-----
<the complete, exact test file content, verbatim>
-----END FILE {nonce}-----

Do not include any narration, preamble, postamble, or Markdown code
fences around these markers. Anything outside the markers is
discarded.
"""


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    if repo_root is None:
        repo_root = Path.cwd()
    repo_root = Path(repo_root)

    component_id = _dual_get(bundle, "component_id")
    criterion_id = _dual_get(bundle, "criterion_id")

    cache_manager_mod = _load_dependency(repo_root, "cache-manager", "cache_manager")
    llm_endpoint_mod = _load_dependency(repo_root, "llm-endpoint", "llm_endpoint")

    criterion_hash = _criterion_hash(bundle)
    gate_inputs_hash = _gate_inputs_hash(seed, PROMPT_VERSION)

    cache_key = cache_manager_mod.CacheKey(
        spec_bundle_hash=criterion_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager_mod.get(cache_key, repo_root=repo_root)
    if _is_cache_hit(cached, cache_manager_mod):
        payload = _dual_get(cached, "payload", {})
        file_info = _dual_get(payload, "file", {})
        return _result(
            component_id=_dual_get(payload, "component_id", component_id),
            criterion_id=_dual_get(payload, "criterion_id", criterion_id),
            model=_dual_get(payload, "model", model),
            seed=seed,
            cache_hit=True,
            file={
                "path": _dual_get(file_info, "path"),
                "content": _dual_get(file_info, "content"),
            },
            model_call_error=None,
        )

    dependency_interfaces = _dual_get(bundle, "dependency_interfaces") or {}
    if not isinstance(dependency_interfaces, dict):
        dependency_interfaces = {}

    nonce = uuid.uuid4().hex
    prompt = _build_prompt(bundle, nonce, dependency_interfaces)

    response = llm_endpoint_mod.complete(prompt=prompt, model=model, backend=llm_backend)
    error = _dual_get(response, "model_call_error")
    if error:
        return _result(
            component_id, criterion_id, model, seed, False, None,
            {
                "category": _dual_get(error, "category", "unknown"),
                "message": _dual_get(error, "message", ""),
            },
        )

    text = _dual_get(response, "text")
    extracted = _extract_file(text, nonce)
    if extracted is None:
        return _result(
            component_id, criterion_id, model, seed, False, None,
            {
                "category": "missing_markers",
                "message": f"no BEGIN/END FILE markers found for nonce {nonce}",
            },
        )

    try:
        ast.parse(extracted)
    except SyntaxError as exc:
        return _result(
            component_id, criterion_id, model, seed, False, None,
            {
                "category": "malformed_code",
                "message": f"SyntaxError: {exc}",
            },
        )

    arity_error = _check_fake_arity(extracted, dependency_interfaces)
    if arity_error is not None:
        return _result(component_id, criterion_id, model, seed, False, None, arity_error)

    slug = _slug(component_id)
    if criterion_id:
        filename = f"test_{criterion_id.lower().replace('-', '_')}.py"
    else:
        filename = "test_unknown.py"
    rel_path = f"verification/{slug}/generated-test/{filename}"
    out_path = repo_root / "verification" / slug / "generated-test" / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(extracted)

    payload = {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "model": model,
        "file": {"path": rel_path, "content": extracted},
    }
    cached_result = cache_manager_mod.CachedResult(
        gate_type="generated_test",
        payload=payload,
        stored_at=cache_manager_mod.now_iso(),
    )
    cache_manager_mod.put(cache_key, cached_result, repo_root=repo_root)

    return _result(
        component_id, criterion_id, model, seed, False,
        {"path": rel_path, "content": extracted},
        None,
    )


def _parse_cli_args(rest):
    positional = []
    options = {"model": None, "seed": 0, "repo_root": Path.cwd(), "format": "text"}
    for arg in rest:
        if arg.startswith("--model="):
            options["model"] = arg.split("=", 1)[1]
        elif arg.startswith("--seed="):
            options["seed"] = int(arg.split("=", 1)[1])
        elif arg.startswith("--repo-root="):
            options["repo_root"] = Path(arg.split("=", 1)[1])
        elif arg.startswith("--format="):
            options["format"] = arg.split("=", 1)[1]
        elif arg.startswith("--"):
            raise ValueError(f"unknown option: {arg}")
        else:
            positional.append(arg)
    return positional, options


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    usage = (
        "usage: hotdocs author-test <component-id> <criterion-id> "
        "--model=<model-id> [--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
    )
    if not argv or argv[0] != "author-test":
        print(usage, file=sys.stderr)
        return 2

    try:
        positional, options = _parse_cli_args(argv[1:])
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if len(positional) != 2 or options["model"] is None:
        print(usage, file=sys.stderr)
        return 2

    component_id, criterion_id = positional
    repo_root = options["repo_root"]

    try:
        assembler_mod = _load_dependency(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
        bundle = assembler_mod.assemble_criterion(component_id, criterion_id, repo_root)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    result = author_test(bundle, options["model"], options["seed"], repo_root=repo_root)
    error = _dual_get(result, "model_call_error")

    if options["format"] == "json":
        print(json.dumps(result, indent=2))
    else:
        if error:
            print(
                f"model call error: {_dual_get(error, 'category')}: "
                f"{_dual_get(error, 'message')}"
            )
        else:
            file_info = _dual_get(result, "file")
            print(f"wrote {_dual_get(file_info, 'path')}")

    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())