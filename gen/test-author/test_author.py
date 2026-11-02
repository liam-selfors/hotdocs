"""Authors generated-test code for one acceptance criterion, from spec prose alone."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

PROMPT_VERSION = "v1"
GATE_VERSION = "generated_test@1.0.0"


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


@dataclass
class TestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: Optional[Dict[str, Any]]
    model_call_error: Optional[Dict[str, Any]]


def _slug_and_module_name(component_id: str):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    return slug, slug.replace("-", "_")


def _load_dependency_module(repo_root: Path, dep_slug: str, module_name: str):
    base = Path(repo_root) / "gen" / dep_slug
    flat_path = base / f"{module_name}.py"
    pkg_path = base / module_name / "__init__.py"

    if flat_path.exists():
        module_path = flat_path
    elif pkg_path.exists():
        module_path = pkg_path
    else:
        raise ModuleNotFoundError(
            f"dependency module '{module_name}' not found under {base}"
        )

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    # Must register before exec_module: a dataclass's class body resolves
    # sys.modules[__module__] while the class body itself is executing.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _criterion_content_hash(bundle) -> str:
    fields = {}
    for key in (
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
    ):
        fields[key] = _get(bundle, key)
    canonical = json.dumps(fields, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _gate_inputs_hash(seed: int, prompt_version: str) -> str:
    canonical = json.dumps({"seed": seed, "prompt_version": prompt_version}, sort_keys=True)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _filename_for(criterion_id: str) -> str:
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _write_file(repo_root: Path, slug: str, criterion_id: str, file_info) -> None:
    path = repo_root / "verification" / slug / "generated-test" / _filename_for(criterion_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _get(file_info, "content", "") or ""
    path.write_text(content)


def _extract_file_content(text, nonce: str):
    if not text:
        return None
    pattern = re.compile(
        r"-----BEGIN FILE " + re.escape(nonce) + r"-----\n(.*?)\n-----END FILE "
        + re.escape(nonce) + r"-----",
        re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return None
    return m.group(1)


def _split_top_level(s: str):
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


def _parse_params_arity(params_str: str):
    parts = _split_top_level(params_str)
    required = 0
    optional = 0
    has_var = False
    for p in parts:
        p = p.strip()
        if not p or p == "*":
            continue
        if p.startswith("**") or p.startswith("*"):
            has_var = True
            continue
        if "=" in p:
            optional += 1
        else:
            required += 1
    return (required, required + optional, has_var)


_SIG_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^()]*)\)\s*->\s*[\w\[\], .|]+")


def _extract_dependency_arities(dependency_interfaces):
    result: Dict[str, list] = {}
    for _dep_id, text in (dependency_interfaces or {}).items():
        if not text:
            continue
        for m in _SIG_RE.finditer(text):
            name, params = m.group(1), m.group(2)
            result.setdefault(name, []).append(_parse_params_arity(params))
    return result


def _arity_of_funcdef(node: ast.FunctionDef):
    nargs = len(node.args.args) + len(node.args.kwonlyargs)
    required_positional = len(node.args.args) - len(node.args.defaults)
    required_kwonly = sum(1 for d in node.args.kw_defaults if d is None)
    required = required_positional + required_kwonly
    has_var = bool(node.args.vararg or node.args.kwarg)
    return (required, nargs, has_var)


def _collect_function_arities(tree: ast.Module):
    func_defs = {}
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            func_defs[node.name] = _arity_of_funcdef(node)
        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                aliases[node.targets[0].id] = node.value.id

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                sub_tree = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            for sub_node in sub_tree.body:
                if isinstance(sub_node, ast.FunctionDef) and sub_node.name not in func_defs:
                    func_defs[sub_node.name] = _arity_of_funcdef(sub_node)

    resolved = dict(func_defs)
    for alias, target in aliases.items():
        seen = set()
        t = target
        while t in aliases and t not in seen:
            seen.add(t)
            t = aliases[t]
        if t in func_defs and alias not in resolved:
            resolved[alias] = func_defs[t]
    return resolved


def _arity_matches_any(fake_arity, dep_arities_list):
    f_req, f_max, f_var = fake_arity
    for d_req, d_max, d_var in dep_arities_list:
        if f_var or d_var:
            return True
        if f_req <= d_max and d_req <= f_max:
            return True
    return False


def _check_fake_arity(tree: ast.Module, dependency_arities):
    if not dependency_arities:
        return []
    resolved = _collect_function_arities(tree)
    failures = []
    for name, arity in resolved.items():
        if name in dependency_arities:
            if not _arity_matches_any(arity, dependency_arities[name]):
                failures.append(
                    {
                        "function": name,
                        "fake_arity": arity,
                        "expected_arities": dependency_arities[name],
                    }
                )
    return failures


def _build_prompt(bundle, component_id: str, module_name: str, nonce: str) -> str:
    criterion_id = _get(bundle, "criterion_id", "") or ""
    covers = _get(bundle, "covers", "") or ""
    criterion_text = _get(bundle, "criterion_text", "") or ""
    requirement_text = _get(bundle, "requirement_text", "") or ""
    interface_text = _get(bundle, "interface", "") or ""
    glossary_text = _get(bundle, "glossary", "") or ""
    dependency_interfaces = _get(bundle, "dependency_interfaces", {}) or {}

    dep_parts = [
        f"### Dependency `{dep_id}` interface\n\n{dep_iface}"
        for dep_id, dep_iface in dependency_interfaces.items()
    ]
    dep_section = "\n\n".join(dep_parts) if dep_parts else "(this component has no dependencies)"

    comp_id_underscored = component_id.replace("-", "_")

    return f"""You are authoring a single Python test file for the acceptance criterion
`{criterion_id}` of component `{component_id}`.

You have NO tool access and NO file access. Answer using only the
information given below in this message.

## Criterion under test

Covers: {covers}

{criterion_text}

## Requirement text ({covers})

{requirement_text}

## Target component's interface contract

{interface_text}

## Glossary

{glossary_text}

## Dependency interfaces

{dep_section}

Any fake you write for a dependency's behavior MUST match that
dependency's real, documented call signature and return shape exactly,
as given above -- never invented or simplified. Worked example: if a
dependency's documented return type has named fields (for instance
`{{"text": ..., "model": ..., "backend": ..., "model_call_error": ...}}`),
your fake MUST expose every one of those fields on the object/dict it
returns, never a bare list, string, or number -- even if the test you
are writing only ever reads one of those fields.

## Importing the component under test

The component under test's own module MUST be imported with the exact
statement:

    import {module_name}

Never infer this from a function name, and never use the component id
itself turned into an identifier (`{comp_id_underscored}` is wrong) --
the correct module name is the component's slug (`comp-` stripped)
with every hyphen replaced by an underscore: `{module_name}`. The
component under test may be laid out as `{module_name}.py` or as a
`{module_name}/` package; a plain `import {module_name}` works either
way. Do NOT use any custom loader for this import -- a custom loader
is only ever needed for the component's own dependencies, described
next.

## How the component under test resolves ITS OWN dependencies

This section describes only how `{module_name}` resolves ITS OWN
dependencies internally -- never how you import `{module_name}` itself
(always the plain `import {module_name}` above).

No dependency is statically importable anywhere in this corpus. Every
component resolves each of its own dependencies dynamically, at
runtime, from:

    <repo_root>/gen/<dependency-slug>/<module_name>.py           (flat module)
    <repo_root>/gen/<dependency-slug>/<module_name>/__init__.py  (package)

where `<module_name>` is the dependency's own slug with every hyphen
replaced by an underscore (never `"__init__"`). This resolution is
never interceptable by name-based `sys.modules` injection or
`mock.patch` -- a correct component does not look a dependency up by
a fixed, guessable name.

To fake a dependency for this test, write a fake module file on disk
under a fresh temporary `repo_root`, laid out as a FLAT module
(`<module_name>.py`) even if the real dependency ships as a package --
every real loader in this corpus checks the flat shape first, so a
flat fake is always found regardless of the real dependency's own
layout.

If you (or the test you write) dynamically load any module from a
file path at runtime, the one correctness-critical step is this
literal pattern -- register the module in `sys.modules` BEFORE calling
`exec_module`, never after:

    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # MUST happen before exec_module
    spec.loader.exec_module(module)

Skipping this ordering crashes on any dependency module that defines a
dataclass: a dataclass's class body resolves `sys.modules[__module__]`
while the class body itself is still executing.

## Reading values the target returns

Every field you read from a value `{module_name}` itself returns --
not only a faked dependency's data -- MUST use dual dict-or-attribute
access, for example:

    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

Never rely on a bare `.attr` access alone: this corpus's components
may legitimately return either a dict or an object exposing the same
fields, in any given round, including `{module_name}` itself.

## Confirming a fake was actually invoked

NEVER assert a fake was used by reaching into `sys.modules` under a
guessed key. Real loaders key `sys.modules` dynamically (often
`repo_root`- or hash-qualified), so any guessed key is unreliable and
may fail even against a fully correct candidate. To confirm a fake
ran, have the fake's own code APPEND its invocation record to a plain
file under a path your test controls -- never an in-process,
module-level list -- then have the test read that file back.

## Synthetic fixtures

If this criterion requires constructing a synthetic fixture component
(its own `component.md`, `requirements/`, `interface/`,
`acceptance/`, a `specs/vars/VAR-*.md` file, or a
`specs/decisions/D<N>.md` file) under a temporary repo root:

- Every frontmatter-bearing document (`component.md`,
  `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) MUST carry `id`,
  `title`, `status`, and `owners`; `status` MUST be exactly one of
  `draft`, `ratified`, or `deprecated`.
- Every `requirements/` file needs a matching `acceptance/` file with
  a `Covers:` tag.
- `status: ratified` also requires a placeholder
  `last_ratified_commit` field.
- A unit file (`constraints.md`, or anything under `requirements/`,
  `interface/`, `acceptance/`) carries NO frontmatter at all.
- Never `import yaml` or any other third-party package that is not
  already installed -- write and parse frontmatter as plain text.
- Any list-valued frontmatter field (`owners`, `depends_on`,
  `realizes`, `uses_var`) MUST use YAML flow style, e.g. `[a, b]` --
  never block style -- this corpus's frontmatter reader does not
  recognize block style as a list.
- The fixture component SHOULD default to `sealed: true` with a
  short, fake `source_path` NOT under `gen/`, UNLESS this criterion
  specifically concerns `realizes`/capability-linkage -- only then
  supply a resolvable `P-<id>` in `realizes`. A sealed fixture is
  exempt from `realizes`-related lint rules entirely.
- If this criterion depends on a precondition the target checks
  against `spec-linter`, call `lint()` against the fixture FIRST and
  assert zero hard-fail findings, before exercising the real behavior
  under test, using exactly this call:

      from spec_linter import lint
      findings = lint(None, repo_root)

  (`paths` first, positionally `None` -- never a single positional
  argument.)

## Timestamp comparisons

If this test asserts a wall-clock "own write time" field falls within
a `[before, after]` window, truncate `before` and `after` to the same
precision the field's own documented format carries (e.g. whole
seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits)
-- never compare a value truncated on write against
microsecond-precision bounds directly.

## Output format

Answer with exactly one test file. Wrap its content EXACTLY as:

-----BEGIN FILE {nonce}-----
<the complete, exact test file content, verbatim>
-----END FILE {nonce}-----

Nothing else may appear between those two marker lines except the
test file's content. Do not wrap the markers themselves in a code
fence. Do not add narration, preamble, or postamble outside the
markers.
"""


def _error_to_dict(err):
    if err is None:
        return None
    if isinstance(err, dict):
        return err
    return {"category": _get(err, "category"), "message": _get(err, "message")}


def author_test(
    bundle,
    model: str,
    seed: int = 0,
    *,
    repo_root: Optional[Path] = None,
    llm_backend=None,
) -> TestAuthoringResult:
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()

    component_id = _get(bundle, "component_id", "") or ""
    criterion_id = _get(bundle, "criterion_id", "") or ""
    dependency_interfaces = _get(bundle, "dependency_interfaces", {}) or {}

    slug, module_name = _slug_and_module_name(component_id)

    cache_manager = _load_dependency_module(repo_root, "cache-manager", "cache_manager")

    criterion_content_hash = _criterion_content_hash(bundle)
    gate_inputs_hash = _gate_inputs_hash(seed, PROMPT_VERSION)
    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=criterion_content_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = _get(cached, "payload", {}) or {}
        file_info = _get(payload, "file", {}) or {}
        file_info = dict(file_info) if file_info else None
        if file_info is not None:
            _write_file(repo_root, slug, criterion_id, file_info)
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
    prompt = _build_prompt(bundle, component_id, module_name, nonce)

    llm_endpoint = _load_dependency_module(repo_root, "llm-endpoint", "llm_endpoint")
    response = llm_endpoint.complete(prompt, model, backend=llm_backend)

    model_call_error = _error_to_dict(_get(response, "model_call_error"))
    if model_call_error:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=model_call_error,
        )

    text = _get(response, "text")
    content = _extract_file_content(text, nonce)
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
                "category": "malformed_response",
                "message": "no matching BEGIN/END FILE marker pair found in model response",
            },
        )

    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={
                "category": "malformed_code",
                "message": f"SyntaxError: {exc}",
            },
        )

    dependency_arities = _extract_dependency_arities(dependency_interfaces)
    mismatches = _check_fake_arity(tree, dependency_arities)
    if mismatches:
        m = mismatches[0]
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
                    f"function '{m['function']}' fake arity {m['fake_arity']} "
                    f"does not match any documented arity {m['expected_arities']}"
                ),
            },
        )

    file_info = {
        "path": f"verification/{slug}/generated-test/{_filename_for(criterion_id)}",
        "content": content,
    }

    payload = {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "model": model,
        "file": file_info,
    }
    cached_result = cache_manager.CachedResult(
        gate_type="generated_test",
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )
    cache_manager.put(cache_key, cached_result, repo_root=repo_root)

    _write_file(repo_root, slug, criterion_id, file_info)

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


def _result_to_dict(result):
    return {
        "component_id": _get(result, "component_id"),
        "criterion_id": _get(result, "criterion_id"),
        "model": _get(result, "model"),
        "seed": _get(result, "seed"),
        "prompt_version": _get(result, "prompt_version"),
        "cache_hit": _get(result, "cache_hit"),
        "file": _get(result, "file"),
        "model_call_error": _get(result, "model_call_error"),
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(prog="hotdocs author-test")
    parser.add_argument("component_id")
    parser.add_argument("criterion_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if exc.code is not None else 2

    repo_root = Path(args.repo_root)

    try:
        spec_bundle_assembler = _load_dependency_module(
            repo_root, "spec-bundle-assembler", "spec_bundle_assembler"
        )
        bundle = spec_bundle_assembler.assemble_criterion(
            args.component_id, args.criterion_id, repo_root
        )
    except Exception as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2

    result = author_test(bundle, args.model, args.seed, repo_root=repo_root)

    model_call_error = _get(result, "model_call_error")

    if args.format == "json":
        print(json.dumps(_result_to_dict(result)))
    else:
        if model_call_error:
            print(f"model call error: {model_call_error}")
        else:
            file_info = _get(result, "file", {}) or {}
            print(f"wrote {_get(file_info, 'path')}")

    return 1 if model_call_error else 0


if __name__ == "__main__":
    sys.exit(main())