import argparse
import ast
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

PROMPT_VERSION = "v1"


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


def _get(obj: Any, field: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(field, default)
    return getattr(obj, field, default)


def _slug(component_id: str) -> str:
    prefix = "comp-"
    return component_id[len(prefix):] if component_id.startswith(prefix) else component_id


def _criterion_test_filename(criterion_id: str) -> str:
    return "test_{}.py".format(criterion_id.lower().replace("-", "_"))


def _load_dependency(repo_root: Path, slug: str):
    module_name = slug.replace("-", "_")
    dep_dir = Path(repo_root) / "gen" / slug
    flat_path = dep_dir / "{}.py".format(module_name)
    pkg_path = dep_dir / module_name / "__init__.py"

    if flat_path.exists():
        path = flat_path
    elif pkg_path.exists():
        path = pkg_path
    else:
        raise ImportError(
            "could not locate dependency '{}' under {} (flat: {}, package: {})".format(
                slug, dep_dir, flat_path, pkg_path
            )
        )

    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _criterion_content_hash(bundle: Any) -> str:
    data = {
        "component_id": _get(bundle, "component_id"),
        "criterion_id": _get(bundle, "criterion_id"),
        "covers": _get(bundle, "covers"),
        "criterion_text": _get(bundle, "criterion_text"),
        "requirement_text": _get(bundle, "requirement_text"),
        "interface": _get(bundle, "interface"),
        "glossary": _get(bundle, "glossary"),
        "dependency_interfaces": _get(bundle, "dependency_interfaces", {}) or {},
    }
    blob = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def _gate_inputs_hash(seed: int, prompt_version: str) -> str:
    blob = json.dumps({"seed": seed, "prompt_version": prompt_version}, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def _build_prompt(bundle: Any, nonce: str) -> str:
    criterion_id = _get(bundle, "criterion_id", "") or ""
    component_id = _get(bundle, "component_id", "") or ""
    covers = _get(bundle, "covers", "") or ""
    criterion_text = _get(bundle, "criterion_text", "") or ""
    requirement_text = _get(bundle, "requirement_text", "") or ""
    interface_text = _get(bundle, "interface", "") or ""
    glossary_text = _get(bundle, "glossary", "") or ""
    dependency_interfaces = _get(bundle, "dependency_interfaces", {}) or {}

    dep_sections = []
    for dep_id, dep_interface in dependency_interfaces.items():
        dep_sections.append("### Dependency `{}` interface\n\n{}".format(dep_id, dep_interface))
    dep_block = "\n\n".join(dep_sections) if dep_sections else "(this component has no dependencies)"

    sections = []

    sections.append(
        "You are authoring a test file for acceptance criterion `{criterion_id}`\n"
        "of component `{component_id}`, which covers requirement `{covers}`.\n\n"
        "You have NO tool access and NO file access. You must answer using only the\n"
        "information given below in this prompt. Do not assume you can read any file\n"
        "that is not reproduced here.".format(
            criterion_id=criterion_id, component_id=component_id, covers=covers
        )
    )

    sections.append(
        "## Criterion (Given/When/Then)\n\n{criterion_text}\n\n"
        "## Covered requirement text (`{covers}`)\n\n{requirement_text}\n\n"
        "## Target component's `interface/` content\n\n{interface_text}\n\n"
        "## Glossary\n\n{glossary_text}".format(
            criterion_text=criterion_text,
            covers=covers,
            requirement_text=requirement_text,
            interface_text=interface_text,
            glossary_text=glossary_text,
        )
    )

    sections.append(
        "## Dependency interfaces\n\n"
        "Each dependency's own real, documented `interface/` content follows. If your\n"
        "test fakes a dependency's behavior, the fake MUST match that dependency's\n"
        "real, documented call signature and return shape EXACTLY -- never invent or\n"
        "simplify one.\n\n"
        "Worked example: if a dependency's documented return type has named fields,\n"
        "e.g. a `Foo` with fields `a` and `b`, your fake MUST return/expose every\n"
        "field (e.g. an object or dict with BOTH `a` and `b` set), even if the test\n"
        "you write only reads `a`. Never return a bare list, string, or number in\n"
        "place of a documented multi-field return type.\n\n"
        "{dep_block}".format(dep_block=dep_block)
    )

    sections.append(
        "## How the component under test resolves ITS OWN dependencies\n\n"
        "This applies only to how the component under test (never this test file's\n"
        "own import of the component under test) resolves its dependencies at\n"
        "runtime. To import the component under test itself, use a plain\n"
        "`import <module_name>` -- never a custom loader for that one import.\n\n"
        "No dependency is statically importable anywhere in this corpus. Every\n"
        "component resolves each of its own dependencies dynamically, at runtime,\n"
        "from:\n\n"
        "  <repo_root>/gen/<dependency-slug>/<module_name>.py        (flat module)\n"
        "  <repo_root>/gen/<dependency-slug>/<module_name>/__init__.py (package)\n\n"
        "where `<module_name>` is `<dependency-slug>` with every `-` replaced by `_`\n"
        "(never `\"__init__\"`). This lookup is never interceptable by name-based\n"
        "`sys.modules` injection or `mock.patch` -- the loader always re-derives the\n"
        "path itself.\n\n"
        "To fake a dependency for this test, write a fake module file under a FRESH\n"
        "TEMPORARY `repo_root` (never the real one), always using the FLAT module\n"
        "shape (a single `.py` file, never a package directory) -- every real loader\n"
        "checks the flat shape first.\n\n"
        "The one correctness-critical step, as a literal worked snippet -- the\n"
        "module MUST be registered in `sys.modules` BEFORE `exec_module` is called,\n"
        "because a dataclass's class body resolves `sys.modules[__module__]` while\n"
        "executing:\n\n"
        "```python\n"
        "import importlib.util\n"
        "import sys\n\n"
        "spec = importlib.util.spec_from_file_location(module_name, fake_module_path)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules[module_name] = module  # MUST happen before exec_module\n"
        "spec.loader.exec_module(module)\n"
        "```"
    )

    sections.append(
        "## Synthetic fixtures: frontmatter rules\n\n"
        "If your test constructs a synthetic spec-corpus fixture (a fake\n"
        "`component.md`, `specs/vars/VAR-*.md`, or `specs/decisions/D<N>.md`), EVERY\n"
        "one of those frontmatter-bearing documents MUST carry these frontmatter\n"
        "fields: `id`, `title`, `status`, `owners` -- always required. `status` MUST\n"
        "be exactly one of `draft`, `ratified`, or `deprecated`. If `status:\n"
        "ratified`, also set a placeholder `last_ratified_commit` field. For every\n"
        "fixture component (not only the target under test), every file you create\n"
        "under `requirements/` needs a matching file under `acceptance/` carrying a\n"
        "`Covers:` tag.\n\n"
        "The OPPOSITE also holds: a unit file -- `constraints.md`, or anything under\n"
        "`requirements/`, `interface/`, or `acceptance/` -- carries NO frontmatter at\n"
        "all. Do not add frontmatter to those.\n\n"
        "Any list-valued frontmatter field (`owners`, `depends_on`, `realizes`,\n"
        "`uses_var`) MUST use YAML flow style, e.g. `owners: [lselfors]` -- never\n"
        "block style, e.g.:\n\n"
        "```\n"
        "owners:\n"
        "  - lselfors\n"
        "```\n\n"
        "This corpus's frontmatter reader does not recognize block style as a list\n"
        "at all.\n\n"
        "Your test MUST NEVER `import yaml` or any other third-party package that is\n"
        "not already installed. Write and parse frontmatter as plain text (e.g.\n"
        "simple line splitting/string formatting), not with a YAML library.\n\n"
        "A synthetic fixture SHOULD default to `sealed: true` with a short, fake\n"
        "`source_path` that is NOT under `gen/`, unless this criterion specifically\n"
        "concerns `realizes`/capability-linkage. Only when the criterion genuinely\n"
        "needs `realizes`-driven behavior should the fixture instead supply a\n"
        "resolvable `P-<id>` and leave the fixture unsealed."
    )

    sections.append(
        "## Precondition self-checks\n\n"
        "Whenever your test constructs a synthetic fixture and the criterion depends\n"
        "on a precondition the target component checks against `spec-linter`, the\n"
        "test MUST call `lint()` against the fixture first and assert zero hard-fail\n"
        "findings BEFORE exercising the real behavior under test. This is a literal\n"
        "worked snippet, not a paraphrase -- call it exactly like this (note:\n"
        "`paths` first, positionally `None`, never a single positional argument):\n\n"
        "```python\n"
        "findings = lint(None, repo_root)\n"
        "assert not [f for f in findings if f.severity == \"hard-fail\"]\n"
        "```\n\n"
        "(Adapt the exact hard-fail check to however `lint()`'s real return shape\n"
        "documents a finding's severity -- but the call itself MUST be\n"
        "`lint(None, repo_root)`.)"
    )

    sections.append(
        "## Reading values the target component returns\n\n"
        "Any field you read from a value the TARGET COMPONENT UNDER TEST itself\n"
        "returns (not only a faked dependency's data) MUST be read with dual\n"
        "dict-or-attribute access, e.g.:\n\n"
        "```python\n"
        "def field(obj, name, default=None):\n"
        "    if isinstance(obj, dict):\n"
        "        return obj.get(name, default)\n"
        "    return getattr(obj, name, default)\n"
        "```\n\n"
        "Never assume the target's return value is one fixed shape -- this corpus's\n"
        "convention allows either a dict or an object in a given round."
    )

    sections.append(
        "## Asserting a fake actually ran\n\n"
        "Never assert that a fake was used by reaching into `sys.modules` under a\n"
        "guessed key -- real loaders key dynamically (often qualified by `repo_root`\n"
        "or a hash), so any guessed key is unreliable. Instead, have your fake's own\n"
        "code record its invocation (e.g. append to a list it defines at module\n"
        "scope) and assert against that record."
    )

    sections.append(
        "## Wall-clock timestamp assertions\n\n"
        "If your test asserts that a wall-clock \"own write time\" field falls within\n"
        "a `[before, after]` window, truncate `before` and `after` to the SAME\n"
        "precision the field's own documented format carries (e.g. truncate to whole\n"
        "seconds if the documented example is `%Y-%m-%dT%H:%M:%SZ` with no\n"
        "fractional digits). Never compare a truncated-on-write timestamp against\n"
        "microsecond-precision bounds directly."
    )

    sections.append(
        "## Output format\n\n"
        "Wrap your test file's complete, exact content exactly as follows, with no\n"
        "other text before, inside (besides the file content), or after the markers\n"
        "-- no narration, no code fence, no preamble or postamble outside the\n"
        "markers:\n\n"
        "-----BEGIN FILE {nonce}-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE {nonce}-----\n\n"
        "Everything outside the BEGIN/END markers is discarded. Produce exactly one\n"
        "such block.".format(nonce=nonce)
    )

    return "\n\n".join(sections)


def _extract_file(text: str, nonce: str) -> Optional[str]:
    pattern = re.compile(
        r"-----BEGIN FILE " + re.escape(nonce) + r"-----\s*\n(.*?)\n-----END FILE " + re.escape(nonce) + r"-----",
        re.DOTALL,
    )
    match = pattern.search(text or "")
    if not match:
        return None
    return match.group(1)


def _split_params(args_str: str):
    args_str = args_str.strip()
    if not args_str:
        return []
    parts = []
    depth = 0
    current = ""
    for ch in args_str:
        if ch in "[({":
            depth += 1
        elif ch in "])}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


_SIG_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)\s*->\s*[^\n`]+")


def _parse_dependency_signatures(dependency_interfaces: dict):
    sigs = {}
    for _dep_id, text in (dependency_interfaces or {}).items():
        if not text:
            continue
        for match in _SIG_RE.finditer(text):
            name, args_str = match.group(1), match.group(2)
            params = _split_params(args_str)
            has_var = any(p.startswith("*") for p in params)
            count = sum(1 for p in params if not p.startswith("*"))
            sigs[name] = (count, has_var)
    return sigs


def _collect_func_defs(tree: ast.AST):
    func_defs = {}
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            count = len(args.args) + len(args.kwonlyargs)
            has_var = bool(args.vararg or args.kwarg)
            func_defs[node.name] = (count, has_var)
        elif isinstance(node, ast.Assign):
            if (
                len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                aliases[node.targets[0].id] = node.value.id
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner_tree = ast.parse(node.value)
            except SyntaxError:
                continue
            inner_funcs, inner_aliases = _collect_func_defs(inner_tree)
            func_defs.update(inner_funcs)
            aliases.update(inner_aliases)
    return func_defs, aliases


def _resolve(name, func_defs, aliases, seen=None):
    seen = seen or set()
    if name in seen:
        return None
    seen.add(name)
    if name in func_defs:
        return func_defs[name]
    if name in aliases:
        return _resolve(aliases[name], func_defs, aliases, seen)
    return None


def _check_fake_arity(code: str, bundle: Any) -> Optional[str]:
    dependency_interfaces = _get(bundle, "dependency_interfaces", {}) or {}
    sigs = _parse_dependency_signatures(dependency_interfaces)
    if not sigs:
        return None

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    func_defs, aliases = _collect_func_defs(tree)
    candidate_names = set(func_defs) | set(aliases)

    for name in candidate_names:
        if name not in sigs:
            continue
        resolved = _resolve(name, func_defs, aliases)
        if resolved is None:
            continue
        count, has_var = resolved
        expected_count, expected_has_var = sigs[name]
        if has_var or expected_has_var:
            continue
        if count != expected_count:
            return "{}: expected {} parameter(s), fake defines {}".format(name, expected_count, count)
    return None


def _write_output(repo_root: Path, file_payload: dict) -> None:
    path = Path(repo_root) / _get(file_payload, "path")
    content = _get(file_payload, "content")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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

    cache_manager = _load_dependency(repo_root, "cache-manager")

    criterion_hash = _criterion_content_hash(bundle)
    gate_inputs_hash = _gate_inputs_hash(seed, PROMPT_VERSION)
    gate_version = "generated_test@{}".format(PROMPT_VERSION)

    cache_key = cache_manager.CacheKey(
        spec_bundle_hash=criterion_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=gate_version,
        model_pin=model,
    )

    cached = cache_manager.get(cache_key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = _get(cached, "payload", {}) or {}
        file_payload = _get(payload, "file")
        _write_output(repo_root, file_payload)
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=True,
            file=file_payload,
            model_call_error=None,
        )

    llm_endpoint = _load_dependency(repo_root, "llm-endpoint")

    nonce = uuid.uuid4().hex
    prompt = _build_prompt(bundle, nonce)

    response = llm_endpoint.complete(prompt, model, backend=llm_backend)
    text = _get(response, "text")
    error = _get(response, "model_call_error")

    if error is not None or text is None:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error=error or {"category": "unknown", "message": "no response text"},
        )

    extracted = _extract_file(text, nonce)
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
                "category": "missing_markers",
                "message": "no BEGIN/END FILE marker pair found for the expected nonce",
            },
        )

    try:
        ast.parse(extracted)
    except SyntaxError as exc:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={"category": "malformed_code", "message": str(exc)},
        )

    mismatch = _check_fake_arity(extracted, bundle)
    if mismatch is not None:
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=None,
            model_call_error={"category": "fake_signature_mismatch", "message": mismatch},
        )

    filename = _criterion_test_filename(criterion_id)
    file_payload = {
        "path": "verification/{}/generated-test/{}".format(_slug(component_id), filename),
        "content": extracted,
    }

    cached_result = cache_manager.CachedResult(
        gate_type="generated_test",
        payload={
            "component_id": component_id,
            "criterion_id": criterion_id,
            "model": model,
            "file": file_payload,
        },
        stored_at=cache_manager.now_iso(),
    )
    cache_manager.put(cache_key, cached_result, repo_root=repo_root)

    _write_output(repo_root, file_payload)

    return TestAuthoringResult(
        component_id=component_id,
        criterion_id=criterion_id,
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=False,
        file=file_payload,
        model_call_error=None,
    )


def main(argv=None) -> int:
    raw_argv = list(sys.argv[1:]) if argv is None else list(argv)

    if not raw_argv or raw_argv[0] != "author-test":
        print(
            "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
            "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]",
            file=sys.stderr,
        )
        return 2

    args = raw_argv[1:]
    parser = argparse.ArgumentParser(prog="hotdocs author-test", add_help=False)
    parser.add_argument("component_id")
    parser.add_argument("criterion_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--format", default="text", choices=["json", "text"])

    try:
        parsed = parser.parse_args(args)
    except SystemExit:
        return 2

    repo_root = Path(parsed.repo_root) if parsed.repo_root else Path.cwd()

    try:
        spec_bundle_assembler = _load_dependency(repo_root, "spec-bundle-assembler")
    except Exception as exc:
        print("error: could not load spec-bundle-assembler: {}".format(exc), file=sys.stderr)
        return 2

    try:
        bundle = spec_bundle_assembler.assemble_criterion(parsed.component_id, parsed.criterion_id, repo_root)
    except Exception as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2

    result = author_test(bundle, parsed.model, parsed.seed, repo_root=repo_root)
    error = _get(result, "model_call_error")

    if parsed.format == "json":
        print(json.dumps(asdict(result)))
    else:
        if error:
            print("model-call error: {}".format(error))
        else:
            file_payload = _get(result, "file") or {}
            print("wrote {}".format(_get(file_payload, "path")))

    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())