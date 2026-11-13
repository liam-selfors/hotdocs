"""test-author: authors one generated-test criterion's test code from spec prose alone."""

import argparse
import ast
import dataclasses
import hashlib
import importlib.util
import json
import re
import secrets
import sys
import textwrap
from collections.abc import Mapping
from pathlib import Path

PROMPT_VERSION = "v1"
GATE_TYPE = "generated_test"
GATE_VERSION = GATE_TYPE + "@1.0.0"

_BUNDLE_FIELDS = (
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
    "module_names",
)


@dataclasses.dataclass
class TestAuthoringResult:
    __test__ = False

    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: dict
    model_call_error: dict


def _field(value, name, default=None):
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _text(bundle, name):
    return str(_field(bundle, name) or "")


def _tool_root():
    return next(p for p in Path(__file__).resolve().parents if p.name == "gen").parent


def _load_dependency(repo_root, slug, module_name):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / (module_name + ".py")
    locations = None
    if not path.is_file():
        path = base / module_name / "__init__.py"
        locations = [str(path.parent)]
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    load_name = "_test_author_dep_%s_%s" % (module_name, digest)
    spec = importlib.util.spec_from_file_location(
        load_name, path, submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(value):
    data = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _criterion_hash(bundle):
    return _sha256({name: _field(bundle, name) for name in _BUNDLE_FIELDS})


def _gate_inputs_hash(seed):
    return _sha256({"seed": seed, "prompt_version": PROMPT_VERSION})


def _test_path(component_id, criterion_id):
    slug = component_id.removeprefix("comp-")
    filename = "test_%s.py" % criterion_id.lower().replace("-", "_")
    return "verification/%s/generated-test/%s" % (slug, filename)


def _write(root, path, content):
    target = Path(root) / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content.encode("utf-8"))


_GUIDANCE = """## How the component under test resolves its own dependencies

No dependency is statically importable. Resolution is dynamic, at runtime, from `<repo_root>/gen/<dependency-slug>/<module_name>.py` (flat) or `.../<module_name>/__init__.py` (package), else the tool's own copy, so omitting one never makes it missing. It is never interceptable by name-based `sys.modules` injection or `mock.patch`.

To fake a dependency, write a fake module file under a fresh temporary `repo_root` -- always flat-module shape, `<repo_root>/gen/<dependency-slug>/<module_name>.py`: every real loader checks flat first. `module_name` is the slug with hyphens replaced by underscores, never `"__init__"`.

The component under test itself needs no custom loader: a plain `import <module_name>` -- exactly the import statement(s) given under "Module under test" below. The generator may lay a module out as `<module>.py` or a `<module>/` package; the import is the same either way.

When the test itself loads any module from a file path, register it in `sys.modules` BEFORE executing it (a dataclass needs this):

```python
import importlib.util, sys
spec = importlib.util.spec_from_file_location(module_name, path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)
```

## Faking a dependency

Any fake you write for a dependency's behavior MUST match that dependency's real, documented call signature and return shape exactly, as given in its interface under "Dependency interfaces" below -- never invented or simplified. A dependency's contract is public; the target's own implementation is not, and you have none of it.

Worked example: the documented signature is `lookup(key: str) -> Record`, and `Record` documents the named fields `name` and `size`. The fake MUST take exactly that one parameter and expose every field:

```python
def lookup(key):
    return {"name": "x", "size": 1}
```

never `return "x"`, `return [1]`, or a bare number -- even if the test reads only `name`.

To confirm a fake was invoked, use a file-based invocation log: the fake's own code appends its invocation record to a file under a path the test controls, and the test reads that file. Never assert a fake was used by reaching into `sys.modules` under a guessed key -- real loaders key dynamically (often `repo_root`- or hash-qualified), so any guess is unreliable -- and never record invocations in an in-process, module-level list.

## Reading values the target returns

Every field read from a value the target itself returns (not only a faked dependency's data) MUST use dual dict-or-attribute access, never assumed to be one shape -- any component may return either a dict or an object:

```python
def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)
```

## Wall-clock timestamps

A test asserting a wall-clock "own write time" field falls within a `[before, after]` window MUST truncate `before`/`after` to the same precision the field's own documented format carries (e.g. whole seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits: `datetime.now(timezone.utc).replace(microsecond=0)`) -- never compare a truncated-on-write timestamp against microsecond-precision bounds directly.

## Synthetic spec fixtures

Every frontmatter-bearing document a fixture constructs (`component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) MUST carry the frontmatter SPEC_GUIDELINES.md requires: `id`, `title`, `status`, `owners`, always, with `status` exactly one of `draft`/`ratified`/`deprecated`. `status: ratified` also sets a placeholder `last_ratified_commit`. A unit file (`constraints.md`, or anything under `requirements/`, `interface/`, `acceptance/`) carries no frontmatter at all. Every `requirements/` file needs a matching `acceptance/` file with a `Covers:` tag, for every fixture component.

Any list-valued frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) MUST use YAML flow style, e.g. `[a, b]`, never block style: this corpus's frontmatter reader does not recognize block style as a list.

A synthetic fixture SHOULD default to `sealed: true` with a short, fake `source_path` not under `gen/` (e.g. `legacy/foo/`), unless the criterion specifically concerns `realizes`/capability-linkage: sealed exempts it from `realizes` and the capability machinery. Only when the criterion genuinely needs `realizes`-driven behavior MUST the fixture supply a resolvable `P-<id>`.

A test MUST NEVER `import yaml` or any other not-already-installed third-party package: write and parse frontmatter as plain text.

Whenever the test constructs a synthetic fixture and the criterion depends on a precondition the target checks against `spec-linter`, the test MUST call `lint()` against the fixture first and assert zero hard-fail findings before exercising the real behavior. Load `spec_linter` from `<tool root>/gen/spec-linter/spec_linter.py` (else `.../spec_linter/__init__.py`), the tool root being the parent of the nearest directory named `gen` above the module under test's `__file__`, with the loader snippet above. The call is exactly `lint(None, repo_root)` -- `paths` first, positionally `None`, never one positional argument:

```python
report = spec_linter.lint(None, repo_root)
hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
assert hard == 0
```
"""


def _build_prompt(bundle, nonce):
    component_id = _text(bundle, "component_id")
    module_names = list(_field(bundle, "module_names") or []) or [
        component_id.removeprefix("comp-").replace("-", "_")
    ]
    imports = "\n".join("import %s" % name for name in module_names)
    dependencies = _field(bundle, "dependency_interfaces") or {}
    dependency_text = "\n\n".join(
        "### %s\n\n%s" % (dep_id, text) for dep_id, text in dependencies.items()
    ) or "(none)"
    return "\n\n".join([
        "You are writing one pytest test file for one acceptance criterion of "
        "component `%s`, from spec prose alone. You have no access to the "
        "implementation under test, and no tool or file access: answer from "
        "this bundle alone. The test MUST exercise the component's public "
        "interface as described below and assert the criterion's Then clause."
        % component_id,
        "## Module under test\n\nImport the module(s) under test with exactly "
        "these statements, in this order:\n\n```python\n%s\n```" % imports,
        "## Criterion %s (Covers: %s)\n\n%s" % (
            _text(bundle, "criterion_id"),
            _text(bundle, "covers"),
            _text(bundle, "criterion_text"),
        ),
        "## Covered requirement\n\n%s" % _text(bundle, "requirement_text"),
        "## Interface of the component under test\n\n%s" % _text(bundle, "interface"),
        "## Dependency interfaces\n\n%s" % dependency_text,
        "## Glossary\n\n%s" % _text(bundle, "glossary"),
        _GUIDANCE,
        "## Reply format\n\nWrap your test file's content exactly as:\n\n"
        "-----BEGIN FILE %s-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE %s-----\n\n"
        "Anything outside these markers is discarded." % (nonce, nonce),
    ])


_SIGNATURE_START = re.compile(r"([A-Za-z_]\w*)\(")
_ARROW = re.compile(r"\s*->")
_PARAM_HEAD = re.compile(r"(\*{1,2})?[A-Za-z_]\w*|\*|/")
_OPEN = "([{"
_CLOSE = ")]}"


def _split_params(text):
    parts = []
    current = ""
    depth = 0
    for ch in text:
        depth += (ch in _OPEN) - (ch in _CLOSE)
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return [part.strip() for part in parts if part.strip()]


def _signatures(text):
    for match in _SIGNATURE_START.finditer(text):
        start = match.end()
        index = start
        depth = 1
        while index < len(text) and depth:
            depth += (text[index] in _OPEN) - (text[index] in _CLOSE)
            index += 1
        if depth or not _ARROW.match(text, index):
            continue
        heads = [re.split(r"[:=]", param, 1)[0].strip() for param in _split_params(text[start:index - 1])]
        if all(_PARAM_HEAD.fullmatch(head) for head in heads):
            yield match.group(1), sum(1 for head in heads if head[0] not in "*/")


def _dependency_arities(dependency_interfaces):
    arities = {}
    for text in dependency_interfaces.values():
        for name, count in _signatures(str(text)):
            arities.setdefault(name, set()).add(count)
    return arities


def _fake_arity(function):
    args = function.args
    if args.vararg or args.kwarg:
        return None
    return len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)


def _arity_mismatch(tree, arities):
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    by_name = {function.name: function for function in functions}
    candidates = [(function.name, function) for function in functions]
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
            and node.value.id in by_name
        ):
            candidates.append((node.targets[0].id, by_name[node.value.id]))
    for name, function in candidates:
        count = _fake_arity(function)
        if name in arities and count is not None and count not in arities[name]:
            expected = " or ".join(str(n) for n in sorted(arities[name]))
            return "fake `%s` takes %d parameter(s); dependency signature takes %s" % (
                name, count, expected,
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                inner = ast.parse(textwrap.dedent(node.value))
            except (SyntaxError, ValueError):
                continue
            mismatch = _arity_mismatch(inner, arities)
            if mismatch:
                return mismatch
    return None


def _extract(text, nonce, dependency_interfaces):
    pattern = re.compile(
        r"-----BEGIN FILE " + nonce + r"-----\n?(.*?)\n?-----END FILE " + nonce + r"-----",
        re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        return None, {
            "category": "missing_file_block",
            "message": "no matching BEGIN/END FILE pair for this call's nonce",
        }
    content = match.group(1)
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        return None, {
            "category": "malformed_code",
            "message": "authored test is not valid Python: %s" % exc.msg,
        }
    mismatch = _arity_mismatch(tree, _dependency_arities(dependency_interfaces))
    if mismatch:
        return None, {"category": "fake_signature_mismatch", "message": mismatch}
    return content, None


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    root = Path(repo_root or Path.cwd())
    component_id = _text(bundle, "component_id")
    criterion_id = _text(bundle, "criterion_id")
    path = _test_path(component_id, criterion_id)

    cache = _load_dependency(root, "cache-manager", "cache_manager")
    key = cache.CacheKey(
        spec_bundle_hash=_criterion_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(seed),
        gate_version=GATE_VERSION,
        model_pin=model,
    )
    cached = cache.get(key, repo_root=root)
    if not isinstance(cached, cache.Miss):
        content = _field(_field(_field(cached, "payload"), "file"), "content")
        _write(root, path, content)
        return TestAuthoringResult(
            component_id, criterion_id, model, seed, PROMPT_VERSION, True,
            {"path": path, "content": content}, None,
        )

    nonce = secrets.token_hex(16)
    endpoint = _load_dependency(root, "llm-endpoint", "llm_endpoint")
    response = endpoint.complete(_build_prompt(bundle, nonce), model, backend=llm_backend)
    error = _field(response, "model_call_error")
    content = None
    if not error:
        content, error = _extract(
            _field(response, "text"), nonce, _field(bundle, "dependency_interfaces") or {}
        )
    if error:
        return TestAuthoringResult(
            component_id, criterion_id, model, seed, PROMPT_VERSION, False, None, error,
        )

    file = {"path": path, "content": content}
    cache.put(
        key,
        cache.CachedResult(
            gate_type=GATE_TYPE,
            payload={
                "component_id": component_id,
                "criterion_id": criterion_id,
                "model": model,
                "seed": seed,
                "prompt_version": PROMPT_VERSION,
                "file": dict(file),
            },
            stored_at=cache.now_iso(),
        ),
        repo_root=root,
    )
    _write(root, path, content)
    return TestAuthoringResult(
        component_id, criterion_id, model, seed, PROMPT_VERSION, False, file, None,
    )


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
    root = Path(args.repo_root)
    assembler = _load_dependency(root, "spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble_criterion(args.component_id, args.criterion_id, root)
    result = author_test(bundle, args.model, args.seed, repo_root=root)
    if args.format == "json":
        print(json.dumps(dataclasses.asdict(result)))
    else:
        print(json.dumps(result.model_call_error) if result.model_call_error else result.file["path"])
    return 1 if result.model_call_error else 0


if __name__ == "__main__":
    sys.exit(main())
