"""Test Author: authors the test code for one generated-test criterion from spec prose alone."""

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
MAX_REPAIRS = 2
HEADER_PREFIX = "# hotdocs-criterion:"
DRIVER_PREFIX = "## Test driver: "
USAGE = (
    "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)
VALUE_FLAGS = ("--model", "--seed", "--repo-root", "--format")
HASH_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")


BLOCK_R_AUTHOR_010 = """The component under test itself needs no custom loader: a plain `import @MODULE@`.
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

BLOCK_R_AUTHOR_011 = """Any fake a test writes for a dependency's behavior MUST match that dependency's real, documented call signature and return shape exactly, as its interface above gives them, never invented or simplified.
Given a documented return type with named fields, a fake MUST return every field, never a bare list, string or number in its place, even when the test reads only one field. For a dependency that documents

    bar_get(key: str) -> Entry
    Entry: {"key": str, "value": str, "stored_at": str}

a correct fake is

    def bar_get(key):
        return {"key": key, "value": "v", "stored_at": "2026-01-01T00:00:00Z"}

and a fake whose body is `return "v"` is wrong."""

BLOCK_R_AUTHOR_012 = """When a test builds a synthetic spec corpus (a fixture) under a temporary `repo_root`:
- Every frontmatter-bearing document it builds (`component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) carries `id`, `title`, `status` and `owners`, always, with `status` exactly one of `draft`, `ratified` or `deprecated`.
- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`.
- Every `requirements/` file of every fixture component has a matching `acceptance/` file with a `Covers:` tag.
- A unit file (`constraints.md`, or anything under `requirements/`, `interface/` or `acceptance/`) carries no frontmatter at all.
- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text."""

BLOCK_R_AUTHOR_013 = """- A fixture component defaults to `sealed: true` with a short, fake `source_path` not under `gen/`, such as `source_path: legacy/foo/`, unless the criterion concerns `realizes` or capability linkage: sealed exempts it from `realizes` and the capability machinery.
- Only a criterion that needs `realizes`-driven behavior has the fixture supply a resolvable `P-<id>`."""

BLOCK_R_AUTHOR_014 = """- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) uses YAML flow style, such as `owners: [a, b]`, never block style (`- a` lines), which the frontmatter reader does not read as a list."""

BLOCK_R_AUTHOR_015 = """- When the criterion depends on a precondition the target checks with `spec-linter`, the test calls `lint()` on the fixture first and asserts zero hard failures before exercising the behavior under test. The call is exactly `lint(None, repo_root)`: `paths` first and positionally `None`, never one positional argument. Every requirement, guarantee and acceptance file the fixture writes starts with its `# <id>` heading line, then a blank line: a file without it fails lint. When the test spec gives the fixture as code, the test copies that code exactly instead of retyping the files.

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

BLOCK_R_AUTHOR_021 = """Every field read from a value the target itself returns, not only a faked dependency's data, MUST use dual dict-or-attribute access, never one assumed shape:

    def field(value, name):
        return value[name] if isinstance(value, dict) else getattr(value, name)"""

BLOCK_R_AUTHOR_022 = """A test MUST NEVER assert a fake was used by reaching into `sys.modules` under a guessed key: real loaders key modules dynamically, often by `repo_root` or a hash, so any guess is unreliable."""

BLOCK_R_AUTHOR_023 = """A test asserting that a wall-clock "own write time" field falls within a `[before, after]` window truncates `before` and `after` to the precision of the field's documented format, such as whole seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits (`datetime.now(timezone.utc).replace(microsecond=0)`), never comparing a timestamp truncated on write against microsecond-precision bounds."""

BLOCK_R_AUTHOR_024 = """To confirm a fake ran, the fake's own code appends one line per call to a log file at a path the test controls, and the test reads that file; never an in-process, module-level list, since the test cannot reliably find the module object that wrote it.
A test builds the source of any file it writes by concatenating strings, with `repr()` for every value it embeds, never with `str.format`, `%` or an f-string over text that holds braces or percent signs."""

BLOCKS = (
    BLOCK_R_AUTHOR_010,
    BLOCK_R_AUTHOR_011,
    BLOCK_R_AUTHOR_012,
    BLOCK_R_AUTHOR_013,
    BLOCK_R_AUTHOR_014,
    BLOCK_R_AUTHOR_015,
    BLOCK_R_AUTHOR_021,
    BLOCK_R_AUTHOR_022,
    BLOCK_R_AUTHOR_023,
    BLOCK_R_AUTHOR_024,
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
    file: object
    model_call_error: object
    repair_attempts: int
    probe_findings: list


class _UsageError(Exception):
    pass


def _get(bundle, name):
    if isinstance(bundle, Mapping):
        return bundle.get(name)
    return getattr(bundle, name, None)


def _text(bundle, name):
    value = _get(bundle, name)
    return "" if value is None else value


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _tool_root():
    return next(p for p in Path(__file__).resolve().parents if p.name == "gen").parent


def _load_dependency(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / (module_name + ".py")
    locations = None
    if not path.is_file():
        path = base / module_name / "__init__.py"
        locations = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=locations
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _drivers(testing):
    return [line[len(DRIVER_PREFIX):] for line in testing.splitlines() if line.startswith(DRIVER_PREFIX)]


def _criterion_hash(bundle):
    values = {key: _text(bundle, key) for key in HASH_KEYS}
    payload = json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _base_prompt(bundle, modules):
    parts = [
        "You write one complete pytest test file for one acceptance criterion of a component, "
        "from its spec alone, never from its implementation. The test exercises the component's "
        "public interface as described below and asserts the criterion's Then clause.",
        "## Component\n" + _text(bundle, "component_id"),
        "## Criterion " + _text(bundle, "criterion_id") + "\nCovers: " + _text(bundle, "covers")
        + "\n\n" + _text(bundle, "criterion_text"),
        "## Covered requirement\n" + _text(bundle, "requirement_text"),
        "## Interface\n" + _text(bundle, "interface"),
        "## Glossary\n" + _text(bundle, "glossary"),
    ]
    dependency_interfaces = _get(bundle, "dependency_interfaces") or {}
    if dependency_interfaces:
        entries = ["### " + dep_id + "\n" + text for dep_id, text in dependency_interfaces.items()]
        parts.append("## Dependency interfaces\n\n" + "\n\n".join(entries))
    testing = _text(bundle, "testing")
    if testing:
        parts.append("## Test spec\n" + testing)
    parts.append(
        "## Module under test\nImport the code under test with exactly these statements:\n"
        + "\n".join("import " + name for name in modules)
    )
    module = modules[0]
    parts.append("## Rules\n\n" + "\n\n".join(block.replace("@MODULE@", module) for block in BLOCKS))
    return "\n\n".join(parts)


def _reply_instruction(nonce):
    return (
        "## Reply format\n"
        "You have no tool or file access: answer from this bundle alone.\n"
        "Wrap your test file's content exactly as:\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----\n"
        "The two marker lines use exactly this nonce, " + nonce + ". "
        "A test that needs markers in a stand-in model's reply builds them from the nonce "
        "it reads when it runs, never from this one."
    )


def _extract(text, nonce):
    pattern = (
        re.escape("-----BEGIN FILE " + nonce + "-----")
        + r"\n(.*?)\n"
        + re.escape("-----END FILE " + nonce + "-----")
    )
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else None


def _probe_repair(source, findings):
    lines = [
        f"{f['kind']} (line {f['line']}): {f['message']}"
        for f in findings
        if f["severity"] == "error"
    ]
    return (
        "## Repair\nYour previous test failed its probe. Its full source:\n\n"
        + source
        + "\n\nIts error findings:\n"
        + "\n".join(lines)
        + "\n\nReply with the complete corrected test file, in the same markers with the fresh nonce below."
    )


def _markers_repair(nonce):
    return (
        "## Repair\n"
        "Your reply held no BEGIN FILE / END FILE marker pair with the nonce " + nonce + ".\n\n"
        "Reply with the complete corrected test file, in the same markers with the fresh nonce below."
    )


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path.cwd() if repo_root is None else Path(repo_root)
    component_id = _text(bundle, "component_id")
    criterion_id = _text(bundle, "criterion_id")
    llm_endpoint = _load_dependency("llm-endpoint", "llm_endpoint", repo_root)
    test_probe = _load_dependency("test-probe", "test_probe", repo_root)

    names = list(_get(bundle, "module_names") or [])
    derived = _slug(component_id).replace("-", "_")
    modules = names or [derived]
    probe_target = names if names else derived
    drivers = _drivers(_text(bundle, "testing"))

    state = {"repair_attempts": 0, "findings": []}

    def result(file, error):
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=file,
            model_call_error=error,
            repair_attempts=state["repair_attempts"],
            probe_findings=state["findings"],
        )

    nonce = secrets.token_hex(16)
    original = _base_prompt(bundle, modules) + "\n\n" + _reply_instruction(nonce)
    prompt = original
    rejected = None
    last_error = None

    for _ in range(MAX_REPAIRS + 1):
        if rejected is not None:
            nonce = secrets.token_hex(16)
            prompt = original + "\n\n" + rejected + "\n\n" + _reply_instruction(nonce)
            state["repair_attempts"] += 1
        response = llm_endpoint.complete(prompt, model, backend=llm_backend)
        error = _field(response, "model_call_error")
        if error is not None:
            return result(None, {"category": _field(error, "category"), "message": _field(error, "message")})
        text = _field(response, "text")
        content = _extract(text, nonce)
        if content is None:
            rejected = _markers_repair(nonce)
            last_error = {
                "category": "missing_file_markers",
                "message": "model reply held no matching BEGIN/END FILE markers; reply began: "
                + repr(text[:200]),
            }
            continue
        report = test_probe.probe(content, bundle, probe_target, drivers=drivers)
        state["findings"] = [
            {key: _field(f, key) for key in ("kind", "severity", "line", "message")}
            for f in (_field(report, "findings") or [])
        ]
        if _field(report, "ok"):
            body = content
            first, _, rest = content.partition("\n")
            if first.startswith(HEADER_PREFIX):
                body = rest
            full = HEADER_PREFIX + " sha256:" + _criterion_hash(bundle) + "\n" + body
            filename = "test_" + criterion_id.lower().replace("-", "_") + ".py"
            rel = "verification/" + _slug(component_id) + "/generated-test/" + filename
            target = repo_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="") as handle:
                handle.write(full)
            return result({"path": rel, "content": full}, None)
        rejected = _probe_repair(content, state["findings"])
        last_error = {
            "category": "test_probe_failed",
            "message": "authored test failed its probe after "
            + str(state["repair_attempts"])
            + " repair attempts",
        }

    return result(None, last_error)


def _parse(tokens):
    positional = []
    options = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            name, eq, value = token.partition("=")
            if name not in VALUE_FLAGS:
                raise _UsageError("unknown argument " + token)
            if not eq:
                if i + 1 >= len(tokens):
                    raise _UsageError(name + " requires a value")
                i += 1
                value = tokens[i]
            options[name] = value
        else:
            positional.append(token)
        i += 1
    if len(positional) != 2:
        raise _UsageError("expected <component-id> and <criterion-id>")
    if "--model" not in options:
        raise _UsageError("missing required --model")
    if options.get("--format", "text") not in ("json", "text"):
        raise _UsageError("--format must be json or text")
    if not re.fullmatch(r"-?[0-9]+", options.get("--seed", "0")):
        raise _UsageError("--seed must be an integer")
    return positional, options


def main(argv=None):
    tokens = sys.argv[1:] if argv is None else list(argv)
    try:
        positional, options = _parse(tokens)
    except _UsageError as exc:
        print("usage error: " + str(exc), file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    component_id, criterion_id = positional
    model = options["--model"]
    fmt = options.get("--format", "text")
    seed = int(options.get("--seed", "0"))
    repo_root = Path(options["--repo-root"]) if "--repo-root" in options else Path.cwd()

    assembler = _load_dependency("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    result = author_test(bundle, model, seed, repo_root=repo_root)
    error = _field(result, "model_call_error")
    if fmt == "json":
        data = dict(result) if isinstance(result, dict) else dataclasses.asdict(result)
        print(json.dumps(data))
    elif error is None:
        print(criterion_id + ": wrote " + str(_field(_field(result, "file"), "path")))
    else:
        print(
            criterion_id + ": model_call_error " + str(_field(error, "category"))
            + ": " + str(_field(error, "message"))
        )
    return 0 if error is None else 1
