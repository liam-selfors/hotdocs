"""Test Author: authors the test code for one generated-test criterion."""

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
PROMPT_VERSION = "v1"

_USAGE = (
    "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
_FLAGS = ("--model", "--seed", "--repo-root", "--format")
_HEADER_PREFIX = "# hotdocs-criterion:"
_MAX_REPAIRS = 2


@dataclasses.dataclass
class TestAuthoringResult:
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


def _get(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _field(bundle, name, default):
    if isinstance(bundle, Mapping):
        value = bundle.get(name, default)
    else:
        value = getattr(bundle, name, default)
    return default if value is None else value


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _derived_module(component_id):
    return _slug(component_id).replace("-", "_")


def _tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load(repo_root, slug):
    name = slug.replace("-", "_")
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / (name + ".py")
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(name, flat)
    else:
        pkg = base / name / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            name, pkg, submodule_search_locations=[str(pkg.parent)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _criterion_header(bundle):
    data = {
        k: _field(bundle, k, "")
        for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    }
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return _HEADER_PREFIX + " sha256:" + _sha256(text)


def _with_header(bundle, content):
    first, _, rest = content.partition("\n")
    if first.startswith(_HEADER_PREFIX):
        content = rest
    return _criterion_header(bundle) + "\n" + content


def _cache_key(cm, bundle, model, seed):
    criterion = {
        k: _field(bundle, k, "")
        for k in (
            "component_id",
            "criterion_id",
            "covers",
            "criterion_text",
            "requirement_text",
            "interface",
            "glossary",
            "testing",
        )
    }
    criterion["dependency_interfaces"] = dict(_field(bundle, "dependency_interfaces", {}))
    criterion["module_names"] = list(_field(bundle, "module_names", []))
    criterion_hash = _sha256(json.dumps(criterion, sort_keys=True, ensure_ascii=False))
    inputs_hash = _sha256(
        json.dumps({"seed": seed, "prompt_version": PROMPT_VERSION}, sort_keys=True)
    )
    return cm.CacheKey(
        spec_bundle_hash="sha256:" + criterion_hash,
        gate_inputs_hash="sha256:" + inputs_hash,
        gate_version=GATE_VERSION,
        model_pin=model,
    )


def _reply_format(nonce):
    return (
        "Reply format: you have no tool or file access and must answer from this prompt alone. "
        "Wrap your test file's content exactly as:\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----"
    )


def _build_prompt(bundle, nonce):
    component_id = _field(bundle, "component_id", "")
    modules = list(_field(bundle, "module_names", [])) or [_derived_module(component_id)]
    deps = _field(bundle, "dependency_interfaces", {})
    parts = [
        "You are writing one pytest test file for one acceptance criterion of component "
        + component_id
        + ", from its spec alone, never its implementation. The test exercises the "
        "component's public interface as described and asserts the criterion's Then clause.",
        "You have no tool or file access: answer from the bundle below alone.",
        "Each module under test is imported with exactly the statement below, in this order:\n"
        + "\n".join("import " + m for m in modules),
        "## Criterion "
        + _field(bundle, "criterion_id", "")
        + "\n\nCovers: "
        + _field(bundle, "covers", "")
        + "\n\n"
        + _field(bundle, "criterion_text", ""),
        "## Covered requirement\n\n" + _field(bundle, "requirement_text", ""),
        "## Interface of the component under test\n\n" + _field(bundle, "interface", ""),
        "## Dependency interfaces"
        + "".join("\n\n### " + dep_id + "\n" + text for dep_id, text in deps.items()),
        "## Testing guidance\n\n" + _field(bundle, "testing", ""),
        "## Glossary\n\n" + _field(bundle, "glossary", ""),
        "## Rules",
    ]
    parts.extend(block.replace("@MODULE@", modules[0]) for block in _BLOCKS)
    parts.append(_reply_format(nonce))
    return "\n\n".join(parts)


def _repair_prompt(original, source, findings, nonce):
    lines = "\n".join(
        str(f["kind"]) + " (line " + str(f["line"]) + "): " + str(f["message"])
        for f in findings
        if f["severity"] == "error"
    )
    return (
        original
        + "\n\nYour previous test file was rejected by an automated probe. Its full source:\n\n"
        + source
        + "\n\nFindings:\n"
        + lines
        + "\n\nReply with the complete corrected test file.\n\n"
        + _reply_format(nonce)
    )


def _extract(text, nonce):
    match = re.search(
        "-----BEGIN FILE " + nonce + "-----\n(.*?)\n-----END FILE " + nonce + "-----",
        text,
        re.S,
    )
    return None if match is None else match.group(1)


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
    component_id = _field(bundle, "component_id", "")
    criterion_id = _field(bundle, "criterion_id", "")
    rel_path = (
        "verification/"
        + _slug(component_id)
        + "/generated-test/test_"
        + criterion_id.lower().replace("-", "_")
        + ".py"
    )

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

    def write(content):
        target = repo_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))

    cm = _load(repo_root, "cache-manager")
    key = _cache_key(cm, bundle, model, seed)
    cached = cm.get(key, repo_root=repo_root)
    if not isinstance(cached, cm.Miss):
        cached_content = _get(_get(_get(cached, "payload"), "file"), "content")
        content = _with_header(bundle, cached_content)
        write(content)
        return result(True, {"path": rel_path, "content": content}, None, 0, [])

    llm = _load(repo_root, "llm-endpoint")
    tp = _load(repo_root, "test-probe")
    modules = list(_field(bundle, "module_names", []))
    module_name = modules or _derived_module(component_id)

    nonce = secrets.token_hex(16)
    original = _build_prompt(bundle, nonce)
    prompt = original
    repairs = 0
    findings = []
    while True:
        response = llm.complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error is not None:
            return result(
                False,
                None,
                {"category": _get(error, "category"), "message": _get(error, "message")},
                repairs,
                findings,
            )
        content = _extract(_get(response, "text"), nonce)
        if content is None:
            return result(
                False,
                None,
                {
                    "category": "no_file_block",
                    "message": "reply holds no matching BEGIN/END FILE marker pair",
                },
                repairs,
                findings,
            )
        report = tp.probe(content, bundle, module_name)
        findings = [dict(f) for f in _get(report, "findings")]
        if _get(report, "ok"):
            break
        if repairs == _MAX_REPAIRS:
            return result(
                False,
                None,
                {
                    "category": "test_probe_failed",
                    "message": "no authored test passed test-probe after "
                    + str(_MAX_REPAIRS)
                    + " repair attempts",
                },
                repairs,
                findings,
            )
        repairs += 1
        nonce = secrets.token_hex(16)
        prompt = _repair_prompt(original, content, findings, nonce)

    final = _with_header(bundle, content)
    file = {"path": rel_path, "content": final}
    cm.put(
        key,
        cm.CachedResult(
            gate_type="generated_test",
            payload={
                "component_id": component_id,
                "criterion_id": criterion_id,
                "model": model,
                "file": dict(file),
                "seed": seed,
                "prompt_version": PROMPT_VERSION,
            },
            stored_at=cm.now_iso(),
        ),
        repo_root=repo_root,
    )
    write(final)
    return result(False, file, None, repairs, findings)


def _usage_error(cause):
    print("usage error: " + cause, file=sys.stderr)
    print(_USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    opts = {}
    positional = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("-"):
            name, eq, value = token.partition("=")
            if name not in _FLAGS:
                return _usage_error("unknown argument " + token)
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(name + " requires a value")
                i += 1
                value = argv[i]
            opts[name] = value
        else:
            positional.append(token)
        i += 1

    if len(positional) != 2:
        return _usage_error("expected <component-id> and <criterion-id>")
    if "--model" not in opts:
        return _usage_error("missing required --model")
    fmt = opts.get("--format", "text")
    if fmt not in ("json", "text"):
        return _usage_error("--format must be json or text")
    seed_text = opts.get("--seed", "0")
    if re.fullmatch("-?[0-9]+", seed_text) is None:
        return _usage_error("--seed must be an integer")

    component_id, criterion_id = positional
    repo_root = Path(opts.get("--repo-root", str(Path.cwd())))
    assembler = _load(repo_root, "spec-bundle-assembler")
    bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    result = author_test(bundle, opts["--model"], int(seed_text), repo_root=repo_root)

    error = _get(result, "model_call_error")
    if fmt == "json":
        print(json.dumps(dataclasses.asdict(result)))
    elif error is None:
        print(criterion_id + ": wrote " + str(_get(_get(result, "file"), "path")))
    else:
        print(
            criterion_id
            + ": model_call_error "
            + str(_get(error, "category"))
            + ": "
            + str(_get(error, "message"))
        )
    return 0 if error is None else 1
