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

USAGE = (
    "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)

HEADER_PREFIX = "# hotdocs-criterion:"


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


# ---------------------------------------------------------------------------
# Field access and dependency loading
# ---------------------------------------------------------------------------

def _field(value, name, default=None):
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _tool_root():
    gen = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
    return gen.parent


def _load_dependency(repo_root, slug, module_name):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / (module_name + ".py")
    if not path.is_file():
        path = base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Prompt blocks (specs/architecture/test-author-prompt.md)
# ---------------------------------------------------------------------------

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

BLOCK_R_AUTHOR_015 = """- When the criterion depends on a precondition the target checks with `spec-linter`, the test calls `lint()` on the fixture first and asserts zero hard failures before exercising the behavior under test. The call is exactly `lint(None, repo_root)`: `paths` first and positionally `None`, never one positional argument.

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(component_id):
    return component_id.removeprefix("comp-")


def _module_names(bundle):
    names = _field(bundle, "module_names") or []
    if names:
        return list(names)
    return [_slug(_field(bundle, "component_id") or "").replace("-", "_")]


def _criterion_hash(bundle):
    data = {
        k: _field(bundle, k, "")
        for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    }
    text = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reply_instruction(nonce):
    return (
        "You have no tool or file access: answer from the bundle above alone.\n"
        "Reply with the complete test file wrapped exactly as follows; anything "
        "outside the markers is discarded:\n"
        "\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----"
    )


def _build_prompt(bundle):
    names = _module_names(bundle)
    module = names[0]
    parts = [
        "You are writing one pytest test file for an acceptance criterion, "
        "from the spec prose below alone.",
        "## Component\n" + str(_field(bundle, "component_id") or ""),
        "## Criterion " + str(_field(bundle, "criterion_id") or ""),
        "Covers: " + str(_field(bundle, "covers") or ""),
        "## Criterion text (Given/When/Then)\n" + str(_field(bundle, "criterion_text") or ""),
        "## Covered requirement\n" + str(_field(bundle, "requirement_text") or ""),
        "## Interface of the component under test\n" + str(_field(bundle, "interface") or ""),
        "## Glossary\n" + str(_field(bundle, "glossary") or ""),
    ]
    deps = _field(bundle, "dependency_interfaces") or {}
    if deps:
        entries = ["## Dependency interfaces"]
        for dep_id, text in deps.items():
            entries.append("### " + dep_id + "\n" + text)
        parts.append("\n\n".join(entries))
    parts.append(
        "## Module under test\n"
        "Import the module under test with exactly this statement, one per module:\n\n"
        + "\n".join("import " + name for name in names)
    )
    parts.append(
        "Write a test that exercises the component's public interface as described "
        "and asserts the criterion's Then clause."
    )
    parts.append("## Rules")
    for block in BLOCKS:
        parts.append(block.replace("@MODULE@", module))
    return "\n\n".join(parts)


def _extract(text, nonce):
    pattern = (
        r"-----BEGIN FILE " + nonce + r"-----\n(.*?)\n-----END FILE " + nonce + r"-----"
    )
    match = re.search(pattern, text or "", re.DOTALL)
    return match.group(1) if match else None


def _error_dict(error):
    return {"category": _field(error, "category"), "message": _field(error, "message")}


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------

def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
    llm_endpoint = _load_dependency(repo_root, "llm-endpoint", "llm_endpoint")
    test_probe = _load_dependency(repo_root, "test-probe", "test_probe")

    component_id = _field(bundle, "component_id")
    criterion_id = _field(bundle, "criterion_id")
    names = _module_names(bundle)
    probe_module = names if _field(bundle, "module_names") else names[0]

    def result(file, error, repairs, findings):
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=file,
            model_call_error=error,
            repair_attempts=repairs,
            probe_findings=findings,
        )

    original = _build_prompt(bundle)
    nonce = secrets.token_hex(16)
    response = llm_endpoint.complete(
        original + "\n\n" + _reply_instruction(nonce), model, backend=llm_backend
    )
    repairs = 0
    findings = []
    while True:
        error = _field(response, "model_call_error")
        if error:
            return result(None, _error_dict(error), repairs, findings)
        content = _extract(_field(response, "text"), nonce)
        if content is None:
            return result(
                None,
                {"category": "no_file_markers",
                 "message": "reply held no matching BEGIN/END FILE markers"},
                repairs,
                findings,
            )
        report = test_probe.probe(content, bundle, probe_module)
        findings = [dict(f) for f in (_field(report, "findings") or [])]
        if _field(report, "ok"):
            break
        if repairs == 2:
            return result(
                None,
                {"category": "test_probe_failed",
                 "message": "authored test failed test-probe after 2 repair attempts"},
                repairs,
                findings,
            )
        repairs += 1
        nonce = secrets.token_hex(16)
        error_lines = [
            str(f.get("kind")) + " (line " + str(f.get("line")) + "): " + str(f.get("message"))
            for f in findings
            if f.get("severity") == "error"
        ]
        repair_prompt = (
            original + "\n\n" + _reply_instruction_placeholder_free(original)
            if False else original
        )
        repair_prompt = (
            repair_prompt
            + "\n\n## Rejected test\n"
            + content
            + "\n\n## Findings\n"
            + "\n".join(error_lines)
            + "\n\nReturn the complete corrected test file.\n\n"
            + _reply_instruction(nonce)
        )
        response = llm_endpoint.complete(repair_prompt, model, backend=llm_backend)

    body = content
    if body.split("\n", 1)[0].startswith(HEADER_PREFIX):
        body = body.partition("\n")[2]
    file_content = HEADER_PREFIX + " sha256:" + _criterion_hash(bundle) + "\n" + body
    filename = "test_" + criterion_id.lower().replace("-", "_") + ".py"
    rel_path = "verification/" + _slug(component_id) + "/generated-test/" + filename
    target = repo_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write(file_content)
    return result({"path": rel_path, "content": file_content}, None, repairs, findings)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _usage_error(cause):
    print("usage error: " + cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    flags = {"--model": None, "--seed": None, "--repo-root": None, "--format": None}
    positional = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("-"):
            name, eq, value = token.partition("=")
            if name not in flags:
                return _usage_error("unknown argument " + token)
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(name + " requires a value")
                i += 1
                value = argv[i]
            flags[name] = value
        else:
            positional.append(token)
        i += 1

    if len(positional) != 2:
        return _usage_error("expected <component-id> and <criterion-id>")
    if flags["--model"] is None:
        return _usage_error("missing required --model")
    fmt = flags["--format"] if flags["--format"] is not None else "text"
    if fmt not in ("json", "text"):
        return _usage_error("--format must be json or text")
    seed_text = flags["--seed"] if flags["--seed"] is not None else "0"
    if not re.fullmatch(r"-?[0-9]+", seed_text):
        return _usage_error("--seed must be an integer")

    component_id, criterion_id = positional
    model = flags["--model"]
    seed = int(seed_text)
    repo_root = Path(flags["--repo-root"]) if flags["--repo-root"] is not None else Path.cwd()

    assembler = _load_dependency(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    result = author_test(bundle, model, seed, repo_root=repo_root)

    error = _field(result, "model_call_error")
    if fmt == "json":
        print(json.dumps(dataclasses.asdict(result)))
    elif error is None:
        print(criterion_id + ": wrote " + str(_field(_field(result, "file"), "path")))
    else:
        print(
            criterion_id + ": model_call_error "
            + str(_field(error, "category")) + ": " + str(_field(error, "message"))
        )
    return 0 if error is None else 1
