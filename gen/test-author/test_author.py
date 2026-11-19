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
PROMPT_VERSION = "v1"

_HEADER_PREFIX = "# hotdocs-criterion:"

USAGE = (
    "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)


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
    repair_attempts: int
    probe_findings: list


# ---------------------------------------------------------------------------
# Prompt blocks (specs/architecture/test-author-prompt.md)
# ---------------------------------------------------------------------------

_BLOCK_010 = """The component under test itself needs no custom loader: a plain `import @MODULE@`.
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

_BLOCK_011 = """Any fake a test writes for a dependency's behavior MUST match that dependency's real, documented call signature and return shape exactly, as its interface above gives them, never invented or simplified.
Given a documented return type with named fields, a fake MUST return every field, never a bare list, string or number in its place, even when the test reads only one field. For a dependency that documents

    bar_get(key: str) -> Entry
    Entry: {"key": str, "value": str, "stored_at": str}

a correct fake is

    def bar_get(key):
        return {"key": key, "value": "v", "stored_at": "2026-01-01T00:00:00Z"}

and a fake whose body is `return "v"` is wrong."""

_BLOCK_012 = """When a test builds a synthetic spec corpus (a fixture) under a temporary `repo_root`:
- Every frontmatter-bearing document it builds (`component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) carries `id`, `title`, `status` and `owners`, always, with `status` exactly one of `draft`, `ratified` or `deprecated`.
- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`.
- Every `requirements/` file of every fixture component has a matching `acceptance/` file with a `Covers:` tag.
- A unit file (`constraints.md`, or anything under `requirements/`, `interface/` or `acceptance/`) carries no frontmatter at all.
- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text."""

_BLOCK_013 = """- A fixture component defaults to `sealed: true` with a short, fake `source_path` not under `gen/`, such as `source_path: legacy/foo/`, unless the criterion concerns `realizes` or capability linkage: sealed exempts it from `realizes` and the capability machinery.
- Only a criterion that needs `realizes`-driven behavior has the fixture supply a resolvable `P-<id>`."""

_BLOCK_014 = """- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) uses YAML flow style, such as `owners: [a, b]`, never block style (`- a` lines), which the frontmatter reader does not read as a list."""

_BLOCK_015 = """- When the criterion depends on a precondition the target checks with `spec-linter`, the test calls `lint()` on the fixture first and asserts zero hard failures before exercising the behavior under test. The call is exactly `lint(None, repo_root)`: `paths` first and positionally `None`, never one positional argument.

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

_BLOCK_021 = """Every field read from a value the target itself returns, not only a faked dependency's data, MUST use dual dict-or-attribute access, never one assumed shape:

    def field(value, name):
        return value[name] if isinstance(value, dict) else getattr(value, name)"""

_BLOCK_022 = """A test MUST NEVER assert a fake was used by reaching into `sys.modules` under a guessed key: real loaders key modules dynamically, often by `repo_root` or a hash, so any guess is unreliable."""

_BLOCK_023 = """A test asserting that a wall-clock "own write time" field falls within a `[before, after]` window truncates `before` and `after` to the precision of the field's documented format, such as whole seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits (`datetime.now(timezone.utc).replace(microsecond=0)`), never comparing a timestamp truncated on write against microsecond-precision bounds."""

_BLOCK_024 = """To confirm a fake ran, the fake's own code appends one line per call to a log file at a path the test controls, and the test reads that file; never an in-process, module-level list, since the test cannot reliably find the module object that wrote it.
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
# Helpers
# ---------------------------------------------------------------------------


def _field(obj, name, default=None):
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_dep(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / (module_name + ".py")
    if not path.is_file():
        path = base / module_name / "__init__.py"
    load_name = (
        "_hotdocs_dep_" + module_name + "_"
        + hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    )
    spec = importlib.util.spec_from_file_location(load_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[load_name] = module
    spec.loader.exec_module(module)
    return module


def _sha256_json(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _criterion_header_hex(bundle):
    return _sha256_json(
        {
            k: _field(bundle, k, "")
            for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")
        }
    )


def _with_header(content, hexdigest):
    first, _, rest = content.partition("\n")
    if first.startswith(_HEADER_PREFIX):
        content = rest
    return _HEADER_PREFIX + " sha256:" + hexdigest + "\n" + content


def _reply_format(nonce):
    return "\n".join(
        [
            "## Reply format",
            "",
            "You have no tool or file access: answer from this prompt alone.",
            "Wrap your test file's content exactly as follows, each marker on a line of its own; "
            "anything outside the markers is discarded:",
            "",
            "-----BEGIN FILE " + nonce + "-----",
            "<the complete, exact test file content, verbatim>",
            "-----END FILE " + nonce + "-----",
        ]
    )


def _extract(text, nonce):
    pattern = (
        re.escape("-----BEGIN FILE " + nonce + "-----")
        + r"\n(.*?)\n"
        + re.escape("-----END FILE " + nonce + "-----")
    )
    match = re.search(pattern, text or "", re.DOTALL)
    return match.group(1) if match else None


def _build_prompt(bundle, modules, dep_ifaces):
    component_id = _field(bundle, "component_id", "") or ""
    criterion_id = _field(bundle, "criterion_id", "") or ""
    parts = [
        "You are writing one pytest test file for acceptance criterion "
        + criterion_id + " of component " + component_id + ".",
        "You have no tool or file access: answer from this bundle alone.",
        "The test exercises the component's public interface as described below and asserts "
        "the criterion's Then clause. You see only the component's interface contract, never its code.",
        "",
        "## Module under test",
        "",
        "Import each module under test with exactly this statement, in this order:",
        "",
    ]
    parts.extend("import " + name for name in modules)
    parts += [
        "",
        "## Criterion " + criterion_id + " (Covers: " + str(_field(bundle, "covers", "") or "") + ")",
        "",
        _field(bundle, "criterion_text", "") or "",
        "",
        "## Covered requirement",
        "",
        _field(bundle, "requirement_text", "") or "",
        "",
        "## Interface",
        "",
        _field(bundle, "interface", "") or "",
        "",
        "## Dependency interfaces",
        "",
    ]
    for dep_id, text in dep_ifaces.items():
        parts += ["### " + dep_id, text, ""]
    parts += [
        "## Testing guidance",
        "",
        _field(bundle, "testing", "") or "",
        "",
        "## Glossary",
        "",
        _field(bundle, "glossary", "") or "",
        "",
        "## Rules",
        "",
    ]
    for block in _BLOCKS:
        parts += [block.replace("@MODULE@", modules[0]), ""]
    return "\n".join(parts)


def _finding_dict(finding):
    return {k: _field(finding, k) for k in ("kind", "severity", "line", "message")}


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path.cwd() if repo_root is None else Path(repo_root)
    component_id = _field(bundle, "component_id", "") or ""
    criterion_id = _field(bundle, "criterion_id", "") or ""
    dep_ifaces = dict(_field(bundle, "dependency_interfaces", None) or {})
    module_names = list(_field(bundle, "module_names", None) or [])

    slug = component_id.removeprefix("comp-")
    derived = slug.replace("-", "_")
    modules = module_names or [derived]
    probe_module = module_names or derived

    rel_path = (
        "verification/" + slug + "/generated-test/test_"
        + criterion_id.lower().replace("-", "_") + ".py"
    )
    header_hex = _criterion_header_hex(bundle)

    def result(cache_hit, file, error, attempts, findings):
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=cache_hit,
            file=file,
            model_call_error=error,
            repair_attempts=attempts,
            probe_findings=findings,
        )

    def write(content):
        target = repo_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))

    cache_manager = _load_dep("cache-manager", "cache_manager", repo_root)
    content_fields = {
        k: _field(bundle, k, "") or ""
        for k in ("component_id", "criterion_id", "covers", "criterion_text",
                  "requirement_text", "interface", "glossary", "testing")
    }
    content_fields["dependency_interfaces"] = dep_ifaces
    content_fields["module_names"] = module_names
    key = cache_manager.CacheKey(
        spec_bundle_hash="sha256:" + _sha256_json(content_fields),
        gate_inputs_hash="sha256:" + _sha256_json({"prompt_version": PROMPT_VERSION, "seed": seed}),
        gate_version=GATE_VERSION,
        model_pin=model,
    )

    cached = cache_manager.get(key, repo_root=repo_root)
    if not isinstance(cached, cache_manager.Miss):
        payload = _field(cached, "payload")
        cached_content = _field(_field(payload, "file"), "content")
        content = _with_header(cached_content, header_hex)
        write(content)
        return result(True, {"path": rel_path, "content": content}, None, 0, [])

    llm_endpoint = _load_dep("llm-endpoint", "llm_endpoint", repo_root)
    test_probe = _load_dep("test-probe", "test_probe", repo_root)

    base_prompt = _build_prompt(bundle, modules, dep_ifaces)
    original_prompt = base_prompt + "\n" + _reply_format(secrets.token_hex(16))
    nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", original_prompt)[-1]
    prompt = original_prompt
    attempts = 0
    findings = []

    while True:
        response = llm_endpoint.complete(prompt, model, backend=llm_backend)
        error = _field(response, "model_call_error")
        if error:
            return result(
                False, None,
                {"category": _field(error, "category"), "message": _field(error, "message")},
                attempts, findings,
            )
        extracted = _extract(_field(response, "text"), nonce)
        if extracted is None:
            return result(
                False, None,
                {"category": "no_file_markers",
                 "message": "the reply held no matching BEGIN/END FILE marker pair"},
                attempts, findings,
            )
        report = test_probe.probe(extracted, bundle, probe_module)
        findings = [_finding_dict(f) for f in (_field(report, "findings") or [])]
        if _field(report, "ok"):
            break
        if attempts == 2:
            return result(
                False, None,
                {"category": "test_probe_failed",
                 "message": "no authored test passed test-probe after 2 repairs"},
                attempts, findings,
            )
        attempts += 1
        nonce = secrets.token_hex(16)
        error_lines = [
            str(f["kind"]) + " (line " + str(f["line"]) + "): " + str(f["message"])
            for f in findings
            if f["severity"] == "error"
        ]
        prompt = (
            original_prompt
            + "\n\n## Rejected test\n\n"
            + "Your previous test file was rejected. Its full source:\n\n"
            + extracted
            + "\n\nIts errors:\n\n"
            + "\n".join(error_lines)
            + "\n\nReply with the complete corrected test file.\n\n"
            + _reply_format(nonce)
        )

    content = _with_header(extracted, header_hex)
    file = {"path": rel_path, "content": content}
    cache_manager.put(
        key,
        cache_manager.CachedResult(
            gate_type="generated_test",
            payload={
                "component_id": component_id,
                "criterion_id": criterion_id,
                "model": model,
                "seed": seed,
                "prompt_version": PROMPT_VERSION,
                "file": dict(file),
            },
            stored_at=cache_manager.now_iso(),
        ),
        repo_root=repo_root,
    )
    write(content)
    return result(False, file, None, attempts, findings)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _usage_error(cause):
    print("usage error: " + cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    tokens = list(sys.argv[1:] if argv is None else argv)
    flags = ("--model", "--seed", "--repo-root", "--format")
    values = {}
    positional = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, eq, value = token.partition("=")
        if name in flags:
            if not eq:
                if i + 1 >= len(tokens):
                    return _usage_error(name + " requires a value")
                i += 1
                value = tokens[i]
            values[name] = value
        elif token.startswith("-"):
            return _usage_error("unknown argument " + token)
        else:
            positional.append(token)
        i += 1

    if len(positional) != 2:
        return _usage_error("expected <component-id> and <criterion-id>")
    if "--model" not in values:
        return _usage_error("missing required --model")
    fmt = values.get("--format", "text")
    if fmt not in ("json", "text"):
        return _usage_error("--format must be json or text")
    seed_text = values.get("--seed", "0")
    if not re.fullmatch(r"-?[0-9]+", seed_text):
        return _usage_error("--seed must be an integer")

    component_id, criterion_id = positional
    repo_root = Path(values.get("--repo-root", str(Path.cwd())))
    assembler = _load_dep("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    result = author_test(bundle, values["--model"], int(seed_text), repo_root=repo_root)

    error = _field(result, "model_call_error")
    if fmt == "json":
        print(json.dumps(dataclasses.asdict(result)))
    elif error is None:
        print(criterion_id + ": wrote " + str(_field(_field(result, "file"), "path")))
    else:
        print(
            criterion_id + ": model_call_error " + str(_field(error, "category"))
            + ": " + str(_field(error, "message"))
        )
    return 0 if error is None else 1


if __name__ == "__main__":
    sys.exit(main())
