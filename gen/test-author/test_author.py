"""test-author: authors one generated-test criterion's test file from spec prose alone."""

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

GATE_VERSION = "generated_test@1.1.0"
GATE_TYPE = "generated_test"
PROMPT_VERSION = "v1"
HEADER_PREFIX = "# hotdocs-criterion:"


@dataclasses.dataclass
class TestAuthoringResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: dict
    model_call_error: dict


TestAuthoringResult.__test__ = False


# ---------------------------------------------------------------------------
# Fixed prompt blocks (specs/architecture/test-author-prompt.md)
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

_BLOCKS = [
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
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _field(bundle, name):
    """Optional CriterionBundle field access (R-AUTHOR-016)."""
    if isinstance(bundle, dict):
        return bundle.get(name)
    return getattr(bundle, name, None)


def _val(value, name):
    """Dual dict-or-attribute access to a dependency's returned value."""
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_dep(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / (module_name + ".py")
    locations = None
    if not path.is_file():
        path = base / module_name / "__init__.py"
        locations = [str(path.parent)]
    load_name = (
        "_test_author_dep_"
        + module_name
        + "_"
        + hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    )
    spec = importlib.util.spec_from_file_location(
        load_name, path, submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    return module


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _test_filename(criterion_id):
    return "test_" + criterion_id.lower().replace("-", "_") + ".py"


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _header(fields):
    return (
        HEADER_PREFIX
        + " sha256:"
        + _sha256(fields["criterion_text"] + "\n" + fields["requirement_text"])
    )


def _with_header(content, header):
    first, _, rest = content.partition("\n")
    if first.startswith(HEADER_PREFIX):
        content = rest
    return header + "\n" + content


def _read_fields(bundle):
    return {
        "component_id": _field(bundle, "component_id") or "",
        "criterion_id": _field(bundle, "criterion_id") or "",
        "covers": _field(bundle, "covers") or "",
        "criterion_text": _field(bundle, "criterion_text") or "",
        "requirement_text": _field(bundle, "requirement_text") or "",
        "interface": _field(bundle, "interface") or "",
        "glossary": _field(bundle, "glossary") or "",
        "dependency_interfaces": dict(_field(bundle, "dependency_interfaces") or {}),
        "module_names": list(_field(bundle, "module_names") or []),
    }


def _modules(fields):
    if fields["module_names"]:
        return fields["module_names"]
    return [_slug(fields["component_id"]).replace("-", "_")]


def _build_prompt(fields, modules, nonce):
    module = modules[0]
    dep_entries = "\n\n".join(
        "### " + dep_id + "\n\n" + text
        for dep_id, text in fields["dependency_interfaces"].items()
    )
    parts = [
        "You are writing one Python pytest test file for one acceptance criterion, "
        "from the spec text in this prompt alone. You have no tool or file access: "
        "answer from this bundle alone. You never see the implementation under test, "
        "only its interface.",
        "Reply with the test file's content wrapped exactly as:\n\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----",
        "## Module under test\n\n"
        "The test imports the module(s) under test with exactly this statement:\n\n"
        + "\n".join("import " + name for name in modules),
        "## Component\n\n" + fields["component_id"],
        "## Criterion " + fields["criterion_id"] + "\n\n"
        "Covers: " + fields["covers"] + "\n\n"
        + fields["criterion_text"]
        + "\n\nThe test MUST exercise the public interface as described and assert "
        "the criterion's Then clause.",
        "## Covered requirement\n\n" + fields["requirement_text"],
        "## Interface\n\n" + fields["interface"],
        "## Dependency interfaces\n\n" + dep_entries,
        "## Glossary\n\n" + fields["glossary"],
        "## Rules",
    ]
    parts.extend(block.replace("@MODULE@", module) for block in _BLOCKS)
    return "\n\n".join(parts)


def _extract(text, nonce):
    pattern = re.compile(
        re.escape("-----BEGIN FILE " + nonce + "-----")
        + r"\n?(.*?)\n?"
        + re.escape("-----END FILE " + nonce + "-----"),
        re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1)


# ---------------------------------------------------------------------------
# Fake-arity check (R-AUTHOR-020)
# ---------------------------------------------------------------------------

_SIG_START = re.compile(r"\b([A-Za-z_]\w*)\(")
_ARROW = re.compile(r"[ \t]*->")


def _arity(args):
    if args.vararg or args.kwarg:
        return None
    return len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)


def _close_paren(text, start):
    depth = 0
    for i in range(start, len(text)):
        char = text[i]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _interface_arities(dependency_interfaces):
    arities = {}
    for text in dependency_interfaces.values():
        for match in _SIG_START.finditer(text):
            end = _close_paren(text, match.end() - 1)
            if end is None or not _ARROW.match(text, end + 1):
                continue
            try:
                tree = ast.parse("def _f(" + text[match.end():end] + "): pass")
            except SyntaxError:
                continue
            arities.setdefault(match.group(1), set()).add(_arity(tree.body[0].args))
    return arities


def _fake_mismatch(tree, sigs):
    defs = {
        node.name: _arity(node.args)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    candidates = list(defs.items())
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
            and node.value.id in defs
        ):
            candidates.append((node.targets[0].id, defs[node.value.id]))
    for name, arity in candidates:
        documented = sigs.get(name)
        if (
            documented is not None
            and arity is not None
            and None not in documented
            and arity not in documented
        ):
            return (
                name
                + ": fake takes "
                + str(arity)
                + " parameter(s), interface documents "
                + " or ".join(str(n) for n in sorted(documented))
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                sub = ast.parse(node.value)
            except (SyntaxError, ValueError):
                continue
            message = _fake_mismatch(sub, sigs)
            if message:
                return message
    return None


# ---------------------------------------------------------------------------
# Library entry point
# ---------------------------------------------------------------------------


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path.cwd() if repo_root is None else Path(repo_root)
    fields = _read_fields(bundle)
    modules = _modules(fields)
    rel_path = (
        "verification/"
        + _slug(fields["component_id"])
        + "/generated-test/"
        + _test_filename(fields["criterion_id"])
    )
    header = _header(fields)

    def result(cache_hit, file, error):
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

    def failure(category, message):
        return result(False, None, {"category": category, "message": message})

    def write(content):
        target = repo_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    cache = _load_dep("cache-manager", "cache_manager", repo_root)
    key = cache.CacheKey(
        spec_bundle_hash="sha256:" + _sha256(json.dumps(fields, sort_keys=True)),
        gate_inputs_hash="sha256:"
        + _sha256(json.dumps({"seed": seed, "prompt_version": PROMPT_VERSION}, sort_keys=True)),
        gate_version=GATE_VERSION,
        model_pin=model,
    )
    cached = cache.get(key, repo_root=repo_root)
    if not isinstance(cached, cache.Miss):
        cached_file = _val(_val(cached, "payload"), "file")
        content = _with_header(_val(cached_file, "content"), header)
        write(content)
        return result(True, {"path": rel_path, "content": content}, None)

    nonce = secrets.token_hex(16)
    prompt = _build_prompt(fields, modules, nonce)
    llm = _load_dep("llm-endpoint", "llm_endpoint", repo_root)
    response = llm.complete(prompt, model, backend=llm_backend)
    error = _val(response, "model_call_error")
    if error:
        return result(False, None, error)

    extracted = _extract(_val(response, "text"), nonce)
    if extracted is None:
        return failure("no_file_block", "response holds no matching BEGIN/END FILE pair")
    try:
        tree = ast.parse(extracted)
    except SyntaxError as exc:
        return failure("malformed_code", "authored test is not valid Python: " + str(exc.msg))
    mismatch = _fake_mismatch(tree, _interface_arities(fields["dependency_interfaces"]))
    if mismatch:
        return failure("fake_signature_mismatch", mismatch)

    content = _with_header(extracted, header)
    file = {"path": rel_path, "content": content}
    cache.put(
        key,
        cache.CachedResult(
            gate_type=GATE_TYPE,
            payload={
                "component_id": fields["component_id"],
                "criterion_id": fields["criterion_id"],
                "model": model,
                "file": file,
            },
            stored_at=cache.now_iso(),
        ),
        repo_root=repo_root,
    )
    write(content)
    return result(False, file, None)


# ---------------------------------------------------------------------------
# CLI
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
    outcome = author_test(bundle, args.model, args.seed, repo_root=repo_root)
    if args.format == "json":
        print(json.dumps(dataclasses.asdict(outcome)))
    elif outcome.model_call_error:
        print("model call error: " + json.dumps(outcome.model_call_error))
    else:
        print(outcome.file["path"])
    return 1 if outcome.model_call_error else 0
