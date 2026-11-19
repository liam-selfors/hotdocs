"""Test Author: authors the test file of one `generated-test` criterion.

The test is written from the criterion's spec prose and the target's
`interface/` contract alone, never from the implementation under test.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import importlib.util
import json
import re
import secrets
import sys
from pathlib import Path

GATE_VERSION = "generated_test@1.2.0"
PROMPT_VERSION = "v1"

_HEADER_PREFIX = "# hotdocs-criterion:"


@dataclasses.dataclass
class TestAuthoringResult:
    __test__ = False

    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: dict | None
    model_call_error: dict | None


# ---------------------------------------------------------------------------
# Prompt blocks (specs/architecture/test-author-prompt.md), verbatim.
# ---------------------------------------------------------------------------

_BLOCK_010 = """\
The component under test itself needs no custom loader: a plain `import @MODULE@`.
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
        return module"""

_BLOCK_011 = """\
Any fake a test writes for a dependency's behavior MUST match that dependency's real, documented call signature and return shape exactly, as its interface above gives them, never invented or simplified.
Given a documented return type with named fields, a fake MUST return every field, never a bare list, string or number in its place, even when the test reads only one field. For a dependency that documents

    bar_get(key: str) -> Entry
    Entry: {"key": str, "value": str, "stored_at": str}

a correct fake is

    def bar_get(key):
        return {"key": key, "value": "v", "stored_at": "2026-01-01T00:00:00Z"}

and a fake whose body is `return "v"` is wrong."""

_BLOCK_012 = """\
When a test builds a synthetic spec corpus (a fixture) under a temporary `repo_root`:
- Every frontmatter-bearing document it builds (`component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) carries `id`, `title`, `status` and `owners`, always, with `status` exactly one of `draft`, `ratified` or `deprecated`.
- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`.
- Every `requirements/` file of every fixture component has a matching `acceptance/` file with a `Covers:` tag.
- A unit file (`constraints.md`, or anything under `requirements/`, `interface/` or `acceptance/`) carries no frontmatter at all.
- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text."""

_BLOCK_013 = """\
- A fixture component defaults to `sealed: true` with a short, fake `source_path` not under `gen/`, such as `source_path: legacy/foo/`, unless the criterion concerns `realizes` or capability linkage: sealed exempts it from `realizes` and the capability machinery.
- Only a criterion that needs `realizes`-driven behavior has the fixture supply a resolvable `P-<id>`."""

_BLOCK_014 = """\
- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) uses YAML flow style, such as `owners: [a, b]`, never block style (`- a` lines), which the frontmatter reader does not read as a list."""

_BLOCK_015 = """\
- When the criterion depends on a precondition the target checks with `spec-linter`, the test calls `lint()` on the fixture first and asserts zero hard failures before exercising the behavior under test. The call is exactly `lint(None, repo_root)`: `paths` first and positionally `None`, never one positional argument.

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
    assert spec_linter.lint(None, repo_root).hard_failures == 0"""

_BLOCK_021 = """\
Every field read from a value the target itself returns, not only a faked dependency's data, MUST use dual dict-or-attribute access, never one assumed shape:

    def field(value, name):
        return value[name] if isinstance(value, dict) else getattr(value, name)"""

_BLOCK_022 = """\
A test MUST NEVER assert a fake was used by reaching into `sys.modules` under a guessed key: real loaders key modules dynamically, often by `repo_root` or a hash, so any guess is unreliable."""

_BLOCK_023 = """\
A test asserting that a wall-clock "own write time" field falls within a `[before, after]` window truncates `before` and `after` to the precision of the field's documented format, such as whole seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits (`datetime.now(timezone.utc).replace(microsecond=0)`), never comparing a timestamp truncated on write against microsecond-precision bounds."""

_BLOCK_024 = """\
To confirm a fake ran, the fake's own code appends one line per call to a log file at a path the test controls, and the test reads that file; never an in-process, module-level list, since the test cannot reliably find the module object that wrote it.
A test builds the source of any file it writes by concatenating strings, with `repr()` for every value it embeds, never with `str.format`, `%` or an f-string over text that holds braces or percent signs."""

_BLOCKS = (
    _BLOCK_010,
    _BLOCK_011,
    _BLOCK_012,
    _BLOCK_013,
    _BLOCK_014,
    _BLOCK_015,
    _BLOCK_021,
    _BLOCK_022,
    _BLOCK_023,
    _BLOCK_024,
)


# ---------------------------------------------------------------------------
# Dependency loading
# ---------------------------------------------------------------------------


def _tool_root() -> Path:
    gen = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
    return gen.parent


def _load_dependency(slug: str, module_name: str, repo_root: Path):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / (module_name + ".py")
    if flat.is_file():
        path = flat
        search = None
    else:
        path = base / module_name / "__init__.py"
        search = [str(path.parent)]
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    load_name = "_test_author_dep_" + module_name + "_" + digest
    spec = importlib.util.spec_from_file_location(
        load_name, path, submodule_search_locations=search
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Value access
# ---------------------------------------------------------------------------


def _val(obj, name):
    return obj[name] if isinstance(obj, dict) else getattr(obj, name)


def _opt(bundle, name, default):
    value = bundle.get(name) if isinstance(bundle, dict) else getattr(bundle, name, None)
    return default if value is None else value


def _bundle_fields(bundle) -> dict:
    return {
        "component_id": _opt(bundle, "component_id", ""),
        "criterion_id": _opt(bundle, "criterion_id", ""),
        "covers": _opt(bundle, "covers", ""),
        "criterion_text": _opt(bundle, "criterion_text", ""),
        "requirement_text": _opt(bundle, "requirement_text", ""),
        "interface": _opt(bundle, "interface", ""),
        "glossary": _opt(bundle, "glossary", ""),
        "dependency_interfaces": dict(_opt(bundle, "dependency_interfaces", {})),
        "module_names": list(_opt(bundle, "module_names", [])),
    }


# ---------------------------------------------------------------------------
# Naming and hashing
# ---------------------------------------------------------------------------


def _slug(component_id: str) -> str:
    return component_id.removeprefix("comp-")


def _module_names(fields: dict) -> list:
    return fields["module_names"] or [_slug(fields["component_id"]).replace("-", "_")]


def _relative_path(fields: dict) -> str:
    filename = "test_" + fields["criterion_id"].lower().replace("-", "_") + ".py"
    return "verification/" + _slug(fields["component_id"]) + "/generated-test/" + filename


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _header_hex(fields: dict) -> str:
    return _sha256(fields["criterion_text"] + "\n" + fields["requirement_text"])


def _with_header(content: str, header_hex: str) -> str:
    first, _, rest = content.partition("\n")
    if first.startswith(_HEADER_PREFIX):
        content = rest
    return _HEADER_PREFIX + " sha256:" + header_hex + "\n" + content


# ---------------------------------------------------------------------------
# Prompt and extraction
# ---------------------------------------------------------------------------


def _build_prompt(fields: dict, nonce: str) -> str:
    modules = _module_names(fields)
    blocks = "\n\n".join(block.replace("@MODULE@", modules[0]) for block in _BLOCKS)
    imports = "\n".join("import " + name for name in modules)
    deps = "".join(
        "\n\n### " + dep_id + "\n" + text
        for dep_id, text in fields["dependency_interfaces"].items()
    )
    return (
        "You are writing one Python pytest test file that checks one acceptance "
        "criterion of one component, from its specification alone.\n"
        "You have no tool or file access: answer from the bundle below alone, "
        "without reading, running or fetching anything.\n"
        "The test exercises the component's public interface as described and "
        "asserts the criterion's `Then` clause.\n"
        "\n"
        "Wrap the test file's content exactly as:\n"
        "\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----\n"
        "\n"
        "Anything outside those two markers is discarded.\n"
        "\n"
        "## Module under test\n"
        "\n"
        "Import each module under test with exactly the statement given here, "
        "one per line, never a name inferred from a function name or from the "
        "component id:\n"
        "\n" + imports + "\n"
        "\n"
        "## Criterion\n"
        "\n"
        "Component: " + fields["component_id"] + "\n"
        "Criterion: " + fields["criterion_id"] + "\n"
        "Covers: " + fields["covers"] + "\n"
        "\n" + fields["criterion_text"] + "\n"
        "\n"
        "## Covered requirement\n"
        "\n" + fields["requirement_text"] + "\n"
        "\n"
        "## Interface of the component under test\n"
        "\n" + fields["interface"] + "\n"
        "\n"
        "## Dependency interfaces" + deps + "\n"
        "\n"
        "## Glossary\n"
        "\n" + fields["glossary"] + "\n"
        "\n"
        "## Rules\n"
        "\n" + blocks + "\n"
    )


def _extract(text: str, nonce: str):
    marker = re.escape(nonce)
    pattern = re.compile(
        "-----BEGIN FILE " + marker + "-----\n?(.*?)\n?-----END FILE " + marker + "-----",
        re.DOTALL,
    )
    match = pattern.search(text)
    return None if match is None else match.group(1)


# ---------------------------------------------------------------------------
# Fake-arity check (best-effort)
# ---------------------------------------------------------------------------

_SIG_NAME = re.compile(r"([A-Za-z_]\w*)\(")
_ARROW = re.compile(r"\s*->")
_PARAM = re.compile(r"(\*{0,2})([A-Za-z_]\w*)\s*(?::.*|=.*)?", re.DOTALL)


def _matching_close(text: str, start: int):
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                return index if char == ")" else None
            depth -= 1
    return None


def _split_top(params: str) -> list:
    parts = []
    current = ""
    depth = 0
    for char in params:
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        current += char
    parts.append(current)
    return [part.strip() for part in parts if part.strip()]


def _parse_params(params: str):
    count = 0
    variadic = False
    for part in _split_top(params):
        if part in ("*", "/"):
            continue
        match = _PARAM.fullmatch(part)
        if match is None:
            return None
        if match.group(1):
            variadic = True
        else:
            count += 1
    return (count, variadic)


def _dependency_arities(dependency_interfaces: dict) -> dict:
    arities = {}
    for text in dependency_interfaces.values():
        for match in _SIG_NAME.finditer(text):
            close = _matching_close(text, match.end())
            if close is None or not _ARROW.match(text, close + 1):
                continue
            arity = _parse_params(text[match.end():close])
            if arity is not None:
                arities.setdefault(match.group(1), []).append(arity)
    return arities


def _function_arity(fn):
    args = fn.args
    count = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    return (count, args.vararg is not None or args.kwarg is not None)


def _fakes(tree) -> list:
    fakes = []
    function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                source = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            for statement in source.body:
                if isinstance(statement, function_types):
                    fakes.append((statement.name, statement))

    top = {}
    for statement in tree.body:
        if isinstance(statement, function_types):
            top[statement.name] = statement
        elif (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and isinstance(statement.value, ast.Name)
            and statement.value.id in top
        ):
            top[statement.targets[0].id] = top[statement.value.id]

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and len(node.args) == 3
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
            and isinstance(node.args[2], ast.Name)
            and node.args[2].id in top
        ):
            func = node.func
            if (isinstance(func, ast.Name) and func.id == "setattr") or (
                isinstance(func, ast.Attribute)
                and func.attr == "setattr"
                and isinstance(func.value, ast.Name)
                and func.value.id == "monkeypatch"
            ):
                fakes.append((node.args[1].value, top[node.args[2].id]))
        elif (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and node.value.id in top
        ):
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    fakes.append((target.attr, top[node.value.id]))
    return fakes


def _fake_mismatch(tree, dependency_interfaces: dict):
    arities = _dependency_arities(dependency_interfaces)
    for name, fn in _fakes(tree):
        expected = arities.get(name)
        if expected is None:
            continue
        count, variadic = _function_arity(fn)
        if variadic or any(dep_variadic or dep_count == count for dep_count, dep_variadic in expected):
            continue
        return (
            "fake " + name + " takes " + str(count) + " parameter(s); dependency "
            + name + " takes " + " or ".join(str(dep_count) for dep_count, _ in expected)
        )
    return None


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def _result(fields, model, seed, cache_hit, file, error):
    return TestAuthoringResult(
        component_id=fields["component_id"],
        criterion_id=fields["criterion_id"],
        model=model,
        seed=seed,
        prompt_version=PROMPT_VERSION,
        cache_hit=cache_hit,
        file=file,
        model_call_error=error,
    )


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def author_test(bundle, model: str, seed: int = 0, *, repo_root: Path = None, llm_backend=None):
    root = Path.cwd() if repo_root is None else Path(repo_root)
    fields = _bundle_fields(bundle)
    relative = _relative_path(fields)
    header_hex = _header_hex(fields)

    cache_manager = _load_dependency("cache-manager", "cache_manager", root)
    key = cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + _sha256(json.dumps(fields, sort_keys=True)),
        gate_inputs_hash="sha256:" + _sha256(
            json.dumps({"prompt_version": PROMPT_VERSION, "seed": seed}, sort_keys=True)
        ),
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager.get(key, repo_root=root)
    if not isinstance(cached, cache_manager.Miss):
        stored = _val(_val(_val(cached, "payload"), "file"), "content")
        content = _with_header(stored, header_hex)
        _write(root, relative, content)
        return _result(fields, model, seed, True, {"path": relative, "content": content}, None)

    llm_endpoint = _load_dependency("llm-endpoint", "llm_endpoint", root)
    nonce = secrets.token_hex(16)
    response = llm_endpoint.complete(_build_prompt(fields, nonce), model, backend=llm_backend)
    error = _val(response, "model_call_error")
    if error is not None:
        return _result(fields, model, seed, False, None, error)

    extracted = _extract(_val(response, "text"), nonce)
    if extracted is None:
        return _result(fields, model, seed, False, None, {
            "category": "missing_file_markers",
            "message": "no matching BEGIN FILE/END FILE marker pair in the response",
        })

    try:
        tree = ast.parse(extracted)
    except SyntaxError as exc:
        return _result(fields, model, seed, False, None, {
            "category": "malformed_code",
            "message": "test file does not parse: " + str(exc),
        })

    mismatch = _fake_mismatch(tree, fields["dependency_interfaces"])
    if mismatch is not None:
        return _result(fields, model, seed, False, None, {
            "category": "fake_signature_mismatch",
            "message": mismatch,
        })

    content = _with_header(extracted, header_hex)
    file = {"path": relative, "content": content}
    cache_manager.put(
        key,
        cache_manager.CachedResult(
            gate_type="generated_test",
            payload={
                "component_id": fields["component_id"],
                "criterion_id": fields["criterion_id"],
                "model": model,
                "seed": seed,
                "prompt_version": PROMPT_VERSION,
                "file": file,
            },
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=root,
    )
    _write(root, relative, content)
    return _result(fields, model, seed, False, file, None)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    tokens = list(sys.argv[1:] if argv is None else argv)
    if tokens and tokens[0] == "author-test":
        tokens = tokens[1:]
    parser = argparse.ArgumentParser(prog="hotdocs author-test")
    parser.add_argument("component_id")
    parser.add_argument("criterion_id")
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    try:
        args = parser.parse_args(tokens)
    except SystemExit:
        return 2

    root = Path(args.repo_root)
    try:
        assembler = _load_dependency("spec-bundle-assembler", "spec_bundle_assembler", root)
        bundle = assembler.assemble_criterion(args.component_id, args.criterion_id, root)
    except Exception as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2

    result = author_test(bundle, args.model, args.seed, repo_root=root)
    if args.format == "json":
        print(json.dumps(dataclasses.asdict(result)))
    elif result.model_call_error is not None:
        print("model call error: " + json.dumps(result.model_call_error))
    else:
        print(result.file["path"])
    return 1 if result.model_call_error is not None else 0


if __name__ == "__main__":
    sys.exit(main())
