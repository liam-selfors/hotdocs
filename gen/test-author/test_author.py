"""test-author: authors the test code for one generated-test criterion."""

import dataclasses
import hashlib
import importlib.util
import json
import re
import secrets
import sys
from collections.abc import Mapping
from pathlib import Path

GATE_VERSION = "generated_test@3.0.0"
GATE_TYPE = "generated_test"
PROMPT_VERSION = "v1"

_HEADER_PREFIX = "# hotdocs-criterion:"
_HEADER_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
_MAX_REPAIRS = 2


@dataclasses.dataclass
class TestAuthoringResult:
    __test__ = False

    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: object
    model_call_error: object
    repair_attempts: int
    probe_findings: list


# --------------------------------------------------------------------------
# Field access helpers
# --------------------------------------------------------------------------

def _bget(bundle, name, default):
    if isinstance(bundle, Mapping):
        return bundle.get(name, default)
    return getattr(bundle, name, default)


def _field(value, name):
    return value[name] if isinstance(value, Mapping) else getattr(value, name)


# --------------------------------------------------------------------------
# Dependency loading
# --------------------------------------------------------------------------

def _tool_root():
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load_dependency(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / (module_name + ".py")
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(module_name, flat)
    else:
        package_dir = base / module_name
        spec = importlib.util.spec_from_file_location(
            module_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Names, paths, hashes
# --------------------------------------------------------------------------

def _slug(component_id):
    return component_id.removeprefix("comp-")


def _derived_module(component_id):
    return _slug(component_id).replace("-", "_")


def _test_path(component_id, criterion_id):
    filename = "test_" + criterion_id.lower().replace("-", "_") + ".py"
    return "verification/" + _slug(component_id) + "/generated-test/" + filename


def _criterion_header_hash(bundle):
    data = {k: (_bget(bundle, k, "") or "") for k in _HEADER_KEYS}
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _criterion_content_hash(bundle):
    data = {
        "component_id": _bget(bundle, "component_id", "") or "",
        "criterion_id": _bget(bundle, "criterion_id", "") or "",
        "covers": _bget(bundle, "covers", "") or "",
        "criterion_text": _bget(bundle, "criterion_text", "") or "",
        "requirement_text": _bget(bundle, "requirement_text", "") or "",
        "interface": _bget(bundle, "interface", "") or "",
        "glossary": _bget(bundle, "glossary", "") or "",
        "testing": _bget(bundle, "testing", "") or "",
        "dependency_interfaces": dict(_bget(bundle, "dependency_interfaces", None) or {}),
        "module_names": list(_bget(bundle, "module_names", None) or []),
    }
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _gate_inputs_hash(seed):
    text = json.dumps({"seed": seed, "prompt_version": PROMPT_VERSION}, sort_keys=True,
                      separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _with_header(header, content):
    first, _, rest = content.partition("\n")
    if first.startswith(_HEADER_PREFIX):
        content = rest
    return header + "\n" + content


# --------------------------------------------------------------------------
# Prompt blocks (specs/architecture/test-author-prompt.md)
# --------------------------------------------------------------------------

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
    _BLOCK_010, _BLOCK_011, _BLOCK_012, _BLOCK_013, _BLOCK_014,
    _BLOCK_015, _BLOCK_021, _BLOCK_022, _BLOCK_023, _BLOCK_024,
)


# --------------------------------------------------------------------------
# Prompt construction and extraction
# --------------------------------------------------------------------------

def _reply_instruction(nonce):
    return (
        "You have no tool or file access: answer from the material in this prompt alone.\n"
        "Reply with the complete test file, wrapped exactly as follows, each marker on a "
        "line of its own, with nothing but the file between them:\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----"
    )


def _build_prompt(bundle, import_names, module):
    component_id = _bget(bundle, "component_id", "") or ""
    dependency_interfaces = _bget(bundle, "dependency_interfaces", None) or {}
    sections = [
        "You are writing one pytest test file for an acceptance criterion of the "
        "component `" + component_id + "`. Work from the spec text below alone; the "
        "implementation is not shown and must not be assumed. The test exercises the "
        "component's public interface as described and asserts the criterion's Then clause.",
        "## Module under test\n\n"
        "Import the module(s) under test with exactly these statements, in this order:\n\n"
        + "\n".join("import " + name for name in import_names)
        + "\n\nThe module may be laid out as a `<module>.py` file or a `<module>/` "
        "package; the import is the same either way.",
        "## Criterion "
        + (_bget(bundle, "criterion_id", "") or "")
        + "\n\nCovers: "
        + (_bget(bundle, "covers", "") or "")
        + "\n\n"
        + (_bget(bundle, "criterion_text", "") or ""),
        "## Covered requirement\n\n" + (_bget(bundle, "requirement_text", "") or ""),
        "## Interface of the component under test\n\n" + (_bget(bundle, "interface", "") or ""),
    ]
    for dep_id, text in dependency_interfaces.items():
        sections.append("## Dependency interface: " + dep_id + "\n\n" + text)
    sections.append("## Glossary\n\n" + (_bget(bundle, "glossary", "") or ""))
    sections.append("## Testing guidance\n\n" + (_bget(bundle, "testing", "") or ""))
    sections.append("## Rules")
    for block in _BLOCKS:
        sections.append(block.replace("@MODULE@", module))
    nonce = secrets.token_hex(16)
    sections.append(_reply_instruction(nonce))
    return "\n\n".join(sections), nonce


def _repair_prompt(original_prompt, source, findings):
    lines = [
        str(f["kind"]) + " (line " + str(f["line"]) + "): " + str(f["message"])
        for f in findings
        if f["severity"] == "error"
    ]
    nonce = secrets.token_hex(16)
    prompt = (
        original_prompt
        + "\n\n## Rejected test\n\nThe test file you wrote was rejected. Its full source:\n\n"
        + source
        + "\n\nIts errors:\n"
        + "\n".join(lines)
        + "\n\nWrite the complete corrected test file.\n\n"
        + _reply_instruction(nonce)
    )
    return prompt, nonce


def _extract(text, nonce):
    match = re.search(
        "-----BEGIN FILE " + nonce + "-----\n(.*?)\n-----END FILE " + nonce + "-----",
        text,
        re.DOTALL,
    )
    return match.group(1) if match else None


def _finding_dict(finding):
    return {k: _field(finding, k) for k in ("kind", "severity", "line", "message")}


def _write(root, rel_path, content):
    path = Path(root) / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


# --------------------------------------------------------------------------
# Library entry point
# --------------------------------------------------------------------------

def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    component_id = _bget(bundle, "component_id", "") or ""
    criterion_id = _bget(bundle, "criterion_id", "") or ""
    rel_path = _test_path(component_id, criterion_id)
    header = _HEADER_PREFIX + " sha256:" + _criterion_header_hash(bundle)

    def result(cache_hit, file, error, repairs, findings):
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=cache_hit,
            file=file,
            model_call_error=error,
            repair_attempts=repairs,
            probe_findings=findings,
        )

    cache_manager = _load_dependency("cache-manager", "cache_manager", root)
    key = cache_manager.CacheKey(
        spec_bundle_hash=_criterion_content_hash(bundle),
        gate_inputs_hash=_gate_inputs_hash(seed),
        gate_version=GATE_VERSION,
        model_pin=model,
    )
    cached = cache_manager.get(key, repo_root=root)
    if not isinstance(cached, cache_manager.Miss):
        payload = _field(cached, "payload")
        content = _with_header(header, _field(_field(payload, "file"), "content"))
        _write(root, rel_path, content)
        return result(True, {"path": rel_path, "content": content}, None, 0, [])

    llm_endpoint = _load_dependency("llm-endpoint", "llm_endpoint", root)
    test_probe = _load_dependency("test-probe", "test_probe", root)

    module_names = list(_bget(bundle, "module_names", None) or [])
    derived = _derived_module(component_id)
    import_names = module_names if module_names else [derived]
    probe_module = module_names if module_names else derived

    original_prompt, nonce = _build_prompt(bundle, import_names, import_names[0])
    prompt = original_prompt
    repairs = 0
    findings = []
    while True:
        response = llm_endpoint.complete(prompt, model, backend=llm_backend)
        error = _field(response, "model_call_error")
        if error is not None:
            err = {"category": _field(error, "category"), "message": _field(error, "message")}
            return result(False, None, err, repairs, findings)
        source = _extract(_field(response, "text"), nonce)
        if source is None:
            err = {
                "category": "extraction_failed",
                "message": "reply held no matching BEGIN/END FILE pair",
            }
            return result(False, None, err, repairs, findings)
        report = test_probe.probe(source, bundle, probe_module)
        findings = [_finding_dict(f) for f in _field(report, "findings")]
        if _field(report, "ok"):
            break
        if repairs == _MAX_REPAIRS:
            err = {
                "category": "test_probe_failed",
                "message": "authored test failed test-probe after "
                + str(_MAX_REPAIRS) + " repair attempts",
            }
            return result(False, None, err, repairs, findings)
        repairs += 1
        prompt, nonce = _repair_prompt(original_prompt, source, findings)

    content = _with_header(header, source)
    accepted = result(False, {"path": rel_path, "content": content}, None, repairs, findings)
    cache_manager.put(
        key,
        cache_manager.CachedResult(
            gate_type=GATE_TYPE,
            payload=dataclasses.asdict(accepted),
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=root,
    )
    _write(root, rel_path, content)
    return accepted


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

_USAGE = (
    "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
_FLAGS = ("--model", "--seed", "--repo-root", "--format")


class _UsageError(Exception):
    pass


def _parse(argv):
    positionals = []
    values = {}
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("-"):
            name, eq, value = token.partition("=")
            if name not in _FLAGS:
                raise _UsageError("unknown argument " + token)
            if not eq:
                if i + 1 == len(argv):
                    raise _UsageError(name + " requires a value")
                i += 1
                value = argv[i]
            values[name] = value
        else:
            positionals.append(token)
        i += 1
    if len(positionals) != 2:
        raise _UsageError("expected <component-id> and <criterion-id>")
    if "--model" not in values:
        raise _UsageError("missing required --model")
    fmt = values.get("--format", "text")
    if fmt not in ("json", "text"):
        raise _UsageError("--format must be json or text")
    seed = values.get("--seed", "0")
    if not re.fullmatch(r"-?[0-9]+", seed):
        raise _UsageError("--seed must be an integer")
    return {
        "component_id": positionals[0],
        "criterion_id": positionals[1],
        "model": values["--model"],
        "seed": int(seed),
        "format": fmt,
        "repo_root": Path(values["--repo-root"]) if "--repo-root" in values else Path.cwd(),
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        opts = _parse(argv)
    except _UsageError as exc:
        print("usage error: " + str(exc), file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    repo_root = opts["repo_root"]
    assembler = _load_dependency("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    bundle = assembler.assemble_criterion(opts["component_id"], opts["criterion_id"], repo_root)
    result = author_test(bundle, opts["model"], opts["seed"], repo_root=repo_root)
    error = _field(result, "model_call_error")
    if opts["format"] == "json":
        print(json.dumps(dataclasses.asdict(result)))
    elif error is None:
        print(opts["criterion_id"] + ": wrote " + str(_field(_field(result, "file"), "path")))
    else:
        print(
            opts["criterion_id"] + ": model_call_error "
            + str(_field(error, "category")) + ": " + str(_field(error, "message"))
        )
    return 0 if error is None else 1
