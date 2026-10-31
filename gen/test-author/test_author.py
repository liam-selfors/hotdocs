"""test-author: authors test code for one generated-test-kind acceptance criterion."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

PROMPT_VERSION = "v1"
GATE_VERSION = "generated_test@1.0.0"


@dataclass
class TestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: dict = None
    model_call_error: dict = None


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_dependency_module(repo_root, slug):
    module_name = slug.replace("-", "_")
    gen_dir = Path(repo_root) / "gen" / slug
    flat_path = gen_dir / f"{module_name}.py"
    pkg_path = gen_dir / module_name / "__init__.py"
    if flat_path.is_file():
        file_path = flat_path
    elif pkg_path.is_file():
        file_path = pkg_path
    else:
        raise FileNotFoundError(
            f"no module found for dependency slug {slug!r} under {gen_dir}"
        )
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _slug(component_id):
    if component_id and component_id.startswith("comp-"):
        return component_id[len("comp-"):]
    return component_id


def _criterion_filename(criterion_id):
    return f"test_{(criterion_id or '').lower().replace('-', '_')}.py"


def _hash_criterion_content(bundle):
    payload = {
        "criterion_id": _get(bundle, "criterion_id"),
        "covers": _get(bundle, "covers"),
        "criterion_text": _get(bundle, "criterion_text"),
        "requirement_text": _get(bundle, "requirement_text"),
        "interface": _get(bundle, "interface"),
        "glossary": _get(bundle, "glossary"),
        "dependency_interfaces": _get(bundle, "dependency_interfaces") or {},
    }
    canonical = json.dumps(payload, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hash_gate_inputs(seed, prompt_version):
    canonical = json.dumps({"seed": seed, "prompt_version": prompt_version}, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_prompt(bundle, nonce):
    component_id = _get(bundle, "component_id", "") or ""
    criterion_id = _get(bundle, "criterion_id", "") or ""
    covers = _get(bundle, "covers", "") or ""
    criterion_text = _get(bundle, "criterion_text", "") or ""
    requirement_text = _get(bundle, "requirement_text", "") or ""
    interface_text = _get(bundle, "interface", "") or ""
    glossary_text = _get(bundle, "glossary", "") or ""
    dependency_interfaces = _get(bundle, "dependency_interfaces") or {}

    dep_sections = []
    for dep_id, dep_iface in dependency_interfaces.items():
        dep_sections.append(f"### Dependency `{dep_id}` interface contract\n\n{dep_iface}\n")
    dep_block = "\n".join(dep_sections) if dep_sections else (
        "(This component has no dependencies with interface content to fake.)"
    )

    return f"""You are authoring a single Python test file for one acceptance
criterion of a software component, using ONLY the material in this
prompt. You have no tool access, no file access, and no ability to
read the target component's actual source code -- write only against
the contracts given below, never against an implementation you might
otherwise guess at.

## Target component

component_id: {component_id}

## Criterion under test

Criterion id: {criterion_id}
Covers: {covers}

Given/When/Then:
{criterion_text}

## The covered requirement's own text ({covers})

{requirement_text}

## Target component's public interface contract

{interface_text}

## Glossary

{glossary_text}

## Dependency interface contracts

Each section below is a dependency's own real, documented contract.
If your test needs to fake a dependency's behavior, the fake MUST
match that dependency's real, documented call signature and return
shape exactly -- never invent or simplify a signature or a return
shape, even if the test only reads one field of it.

{dep_block}

**Worked example -- return shape.** If a dependency's documented
return type is e.g. `CachedResult` with fields `gate_type`, `payload`,
`stored_at`, and your fake only needs the test to read `payload`, your
fake MUST still return an object or dict exposing ALL three fields
(`gate_type`, `payload`, `stored_at`) -- never a bare dict with only
`payload`, never a bare list/string/number, even though the test reads
only one of them.

## How the target component resolves ITS OWN dependencies (NOT how your
## test imports the target component itself)

Your test file imports the component under test the normal way: a
plain `import <module_name>` statement (`module_name` is the target's
own slug with hyphens replaced by underscores) -- never a custom
loader for the component under test itself.

The target component, however, resolves each of ITS OWN dependencies
dynamically, at runtime, never via a static `import` statement and
never interceptable by a name-based `sys.modules` injection or
`mock.patch`. It loads each dependency from:

  `<repo_root>/gen/<dependency-slug>/<module_name>.py` (flat module), or
  `<repo_root>/gen/<dependency-slug>/<module_name>/__init__.py` (package)

where `module_name` is the dependency's own slug with hyphens replaced
by underscores -- never the literal string "__init__".

To fake one of the target's dependencies for your test, write a fake
module file under a fresh temporary `repo_root` you construct for the
test -- ALWAYS as a flat module
(`<repo_root>/gen/<dependency-slug>/<module_name>.py`), never a
package, since every real loader checks the flat shape first.

The one correctness-critical step, which your test MUST follow exactly
whenever it writes its OWN loader for test setup purposes, is
registering the loaded module in `sys.modules` BEFORE calling
`exec_module` on it -- not after:

```python
import importlib.util, sys
spec = importlib.util.spec_from_file_location(module_name, file_path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)
```

A dataclass's class body resolves `sys.modules[__module__]` while its
class body executes -- skip this step and ANY dependency module
defining a dataclass crashes.

## Confirming a fake was actually invoked

Never assert a fake ran by reaching into `sys.modules` under a guessed
key -- real loaders may key dynamically (e.g. by `repo_root` or a
hash), so any guessed key is unreliable, and this applies equally to
an in-process, module-level list read via any `sys.modules` lookup.
To confirm a fake ran, have the fake's own code append an invocation
record to a FILE whose path the test controls and already knows ahead
of time, then have the test read that file afterward -- never an
in-process list.

## Dual dict-or-attribute access

This corpus is duck-typed: any value the TARGET component itself
returns -- not only a faked dependency's data, including the target's
own function's top-level return value itself -- may legitimately be
either a dict or an object in a given round. Every field your test
reads off such a value MUST use dual access, e.g.:

```python
def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
```

Never a bare `.attr` access alone on such a value.

## Synthetic fixtures

If your test needs to construct a synthetic spec-corpus fixture (e.g.
a fake component.md, requirements/, interface/, acceptance/, or
specs/vars/VAR-*.md / specs/decisions/D<N>.md file) to exercise the
target:

- Every frontmatter-bearing document (component.md, specs/vars/VAR-*.md,
  specs/decisions/D<N>.md) MUST include the fields `id`, `title`,
  `status`, `owners` -- `status` MUST be exactly one of `draft`,
  `ratified`, or `deprecated`. If `status: ratified`, also set a
  placeholder `last_ratified_commit` field.
- A unit file -- anything under requirements/, interface/, or
  acceptance/, or a bare constraints.md -- carries NO frontmatter at
  all. Do not apply the rule above to those.
- Every requirements/ file in a fixture component needs a matching
  acceptance/ file with a `Covers:` tag pointing back to it, for EVERY
  fixture component you construct, not only the target.
- Default every fixture component to `sealed: true` with a short,
  fake `source_path` NOT under `gen/`, UNLESS the criterion
  specifically concerns `realizes`/capability-linkage. `sealed: true`
  exempts a component from `realizes` and the capability machinery
  entirely. Only when a criterion genuinely needs `realizes`-driven
  behavior should you give the fixture a resolvable `P-<id>` instead.
- Any list-valued frontmatter field (`owners`, `depends_on`,
  `realizes`, `uses_var`) MUST use YAML flow style, e.g. `[a, b]` --
  never block style (one item per dashed line). This corpus's
  frontmatter reader does not recognize block style as a list.
- NEVER `import yaml` or any other third-party package that isn't
  already installed. Write and parse frontmatter as plain text.

## Self-check before exercising real behavior

If your test constructs a synthetic fixture and the criterion depends
on a precondition the target checks against spec-linter, call
spec-linter's `lint()` against the fixture FIRST and assert there are
zero hard-fail findings, before exercising the real behavior under
test. Call it exactly like this (positional `paths` first, `None`,
then `repo_root` -- never a single positional argument):

```python
findings = lint(None, repo_root)
```

## Timestamp comparisons

If your test asserts a wall-clock "own write time" field falls within
a `[before, after]` window, truncate `before` and `after` to the SAME
precision the field's own documented format carries (e.g. whole
seconds for a `%Y-%m-%dT%H:%M:%SZ`-style format with no fractional
digits) -- never compare a microsecond-precision `before`/`after`
directly against a value that was truncated on write.

## Output format -- read carefully

Wrap your ENTIRE test file's content, and nothing else, exactly as:

-----BEGIN FILE {nonce}-----
<the complete, exact test file content, verbatim>
-----END FILE {nonce}-----

Nothing MUST appear outside those two marker lines -- no code fence,
no narration, no preamble or postamble. Everything between the
markers is extracted verbatim as the test file's content. You have no
tool or file access: answer from the material in this prompt alone.
"""


def _extract_file(text, nonce):
    if not text:
        return None
    pattern = re.compile(
        r"-----BEGIN FILE " + re.escape(nonce) + r"-----\s*\n(.*?)\n?-----END FILE "
        + re.escape(nonce) + r"-----",
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return None
    return m.group(1)


_SIG_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\(((?:[^()]|\([^()]*\))*)\)\s*->\s*"
)


def _split_top_level(s, sep):
    parts = []
    depth = 0
    current = []
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _parse_params(args_str):
    args_str = args_str.strip()
    if not args_str:
        return 0, False
    count = 0
    flexible = False
    for part in _split_top_level(args_str, ","):
        token = part.strip()
        if not token:
            continue
        if token == "*":
            continue
        if token.startswith("*"):
            flexible = True
            continue
        count += 1
    return count, flexible


def _parse_dependency_signatures(dependency_interfaces):
    sigs = {}
    for _dep_id, text in (dependency_interfaces or {}).items():
        if not text:
            continue
        for m in _SIG_RE.finditer(text):
            name, args_str = m.group(1), m.group(2)
            count, flexible = _parse_params(args_str)
            sigs[name] = (count, flexible)
    return sigs


def _ast_func_arity(node):
    args = node.args
    count = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    flexible = args.vararg is not None or args.kwarg is not None
    return count, flexible


def _collect_function_arities(tree):
    arities = {}
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            arities[node.name] = _ast_func_arity(node)
        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                aliases[node.targets[0].id] = node.value.id
    for alias_name in list(aliases.keys()):
        resolved = aliases[alias_name]
        seen = set()
        while resolved in aliases and resolved not in seen:
            seen.add(resolved)
            resolved = aliases[resolved]
        if resolved in arities:
            arities[alias_name] = arities[resolved]
    return arities


def _collect_arities_from_string_literals(tree, arities):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                sub_tree = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            sub_arities = _collect_function_arities(sub_tree)
            for name, val in sub_arities.items():
                arities.setdefault(name, val)
            _collect_arities_from_string_literals(sub_tree, arities)


def _check_fake_arity(content, dependency_interfaces):
    dep_sigs = _parse_dependency_signatures(dependency_interfaces)
    if not dep_sigs:
        return None
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    test_arities = _collect_function_arities(tree)
    _collect_arities_from_string_literals(tree, test_arities)
    for name, (dep_count, dep_flexible) in dep_sigs.items():
        if dep_flexible:
            continue
        if name not in test_arities:
            continue
        test_count, test_flexible = test_arities[name]
        if test_flexible:
            continue
        if test_count != dep_count:
            return {"name": name, "expected": dep_count, "actual": test_count}
    return None


def _write_file(repo_root, rel_path, content):
    out_path = Path(repo_root) / rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path(repo_root) if repo_root else Path.cwd()

    component_id = _get(bundle, "component_id")
    criterion_id = _get(bundle, "criterion_id")
    dependency_interfaces = _get(bundle, "dependency_interfaces") or {}

    cache_manager = _load_dependency_module(repo_root, "cache-manager")
    llm_endpoint = _load_dependency_module(repo_root, "llm-endpoint")

    criterion_content_hash = _hash_criterion_content(bundle)
    gate_inputs_hash = _hash_gate_inputs(seed, PROMPT_VERSION)

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=criterion_content_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = _get(cached, "payload")
        file_info = _get(payload, "file")
        rel_path = _get(file_info, "path")
        content = _get(file_info, "content")
        if rel_path is not None and content is not None:
            _write_file(repo_root, rel_path, content)
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

    nonce = uuid.uuid4().hex
    prompt = _build_prompt(bundle, nonce)

    response = llm_endpoint.complete(prompt, model, backend=llm_backend)
    error = _get(response, "model_call_error")
    if error is not None:
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
    content = _extract_file(text, nonce)
    if content is None:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={
                "category": "missing_marker_pair",
                "message": "no matching BEGIN/END FILE marker pair found in model response",
            },
        )

    try:
        ast.parse(content)
    except SyntaxError as e:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={"category": "malformed_code", "message": str(e)},
        )

    mismatch = _check_fake_arity(content, dependency_interfaces)
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
                    f"{mismatch['name']}: expected {mismatch['expected']} "
                    f"parameter(s), fake defines {mismatch['actual']}"
                ),
            },
        )

    filename = _criterion_filename(criterion_id)
    rel_path = f"verification/{_slug(component_id)}/generated-test/{filename}"
    file_obj = {"path": rel_path, "content": content}

    payload = {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "model": model,
        "file": file_obj,
    }
    result_record = cache_manager.CachedResult(
        gate_type="generated_test",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )
    cache_manager.put(cache_key, result_record, repo_root=repo_root)

    _write_file(repo_root, rel_path, content)

    return TestAuthoringResult(
        component_id=component_id,
        criterion_id=criterion_id,
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        file=file_obj,
        model_call_error=None,
    )


def _usage():
    print(
        "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
        "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]",
        file=sys.stderr,
    )


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)

    if not argv or argv[0] != "author-test":
        _usage()
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
                _usage()
                return 2
        elif arg.startswith("--repo-root="):
            repo_root = Path(arg.split("=", 1)[1])
        elif arg.startswith("--format="):
            fmt = arg.split("=", 1)[1]
        elif arg.startswith("--"):
            _usage()
            return 2
        else:
            positional.append(arg)

    if len(positional) != 2 or model is None or fmt not in ("json", "text"):
        _usage()
        return 2

    component_id, criterion_id = positional

    try:
        assembler = _load_dependency_module(repo_root, "spec-bundle-assembler")
    except Exception as e:
        print(f"error: could not load spec-bundle-assembler: {e}", file=sys.stderr)
        return 2

    try:
        bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    result = author_test(bundle, model, seed, repo_root=repo_root)

    error = _get(result, "model_call_error")

    if fmt == "json":
        print(json.dumps(asdict(result)))
    else:
        if error is not None:
            print(f"model call error: {_get(error, 'category')}: {_get(error, 'message')}")
        else:
            file_info = _get(result, "file")
            print(f"wrote {_get(file_info, 'path')}")

    return 1 if error is not None else 0


if __name__ == "__main__":
    sys.exit(main())