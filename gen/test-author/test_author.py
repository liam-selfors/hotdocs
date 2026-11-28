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

USAGE = (
    "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)

_VALUE_FLAGS = ("--model", "--seed", "--repo-root", "--format")

_HEADER_PREFIX = "# hotdocs-criterion:"


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


BLOCK_R_AUTHOR_010 = "\n".join([
    "The component under test itself needs no custom loader: a plain `import @MODULE@`.",
    "Its own dependencies are resolved differently. No dependency is statically importable: each is loaded at runtime from `<repo_root>/gen/<dependency-slug>/<module_name>.py` (flat) or `<repo_root>/gen/<dependency-slug>/<module_name>/__init__.py` (package), else from the tool's own copy, so omitting one never makes it missing.",
    "A dependency is never interceptable by name-based `sys.modules` injection or `mock.patch`.",
    "To fake a dependency, write a fake module file under a fresh temporary `repo_root`, always in flat-module shape: `<repo_root>/gen/<dependency-slug>/<module_name>.py`. Every real loader checks flat first.",
    "`module_name` is the slug with hyphens replaced by underscores, never `\"__init__\"`.",
    "Whenever a test loads a module from a file path itself, it uses exactly this shape, with `sys.modules[module_name] = module` before `spec.loader.exec_module(module)`, which a dataclass needs:",
    "",
    "    import importlib.util",
    "    import sys",
    "",
    "    def load_module(path, module_name):",
    "        spec = importlib.util.spec_from_file_location(module_name, path)",
    "        module = importlib.util.module_from_spec(spec)",
    "        sys.modules[module_name] = module",
    "        spec.loader.exec_module(module)",
    "        return module",
])

BLOCK_R_AUTHOR_011 = "\n".join([
    "Any fake a test writes for a dependency's behavior MUST match that dependency's real, documented call signature and return shape exactly, as its interface above gives them, never invented or simplified.",
    "Given a documented return type with named fields, a fake MUST return every field, never a bare list, string or number in its place, even when the test reads only one field. For a dependency that documents",
    "",
    "    bar_get(key: str) -> Entry",
    "    Entry: {\"key\": str, \"value\": str, \"stored_at\": str}",
    "",
    "a correct fake is",
    "",
    "    def bar_get(key):",
    "        return {\"key\": key, \"value\": \"v\", \"stored_at\": \"2026-01-01T00:00:00Z\"}",
    "",
    "and a fake whose body is `return \"v\"` is wrong.",
])

BLOCK_R_AUTHOR_012 = "\n".join([
    "When a test builds a synthetic spec corpus (a fixture) under a temporary `repo_root`:",
    "- Every frontmatter-bearing document it builds (`component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) carries `id`, `title`, `status` and `owners`, always, with `status` exactly one of `draft`, `ratified` or `deprecated`.",
    "- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`.",
    "- Every `requirements/` file of every fixture component has a matching `acceptance/` file with a `Covers:` tag.",
    "- A unit file (`constraints.md`, or anything under `requirements/`, `interface/` or `acceptance/`) carries no frontmatter at all.",
    "- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text.",
])

BLOCK_R_AUTHOR_013 = "\n".join([
    "- A fixture component defaults to `sealed: true` with a short, fake `source_path` not under `gen/`, such as `source_path: legacy/foo/`, unless the criterion concerns `realizes` or capability linkage: sealed exempts it from `realizes` and the capability machinery.",
    "- Only a criterion that needs `realizes`-driven behavior has the fixture supply a resolvable `P-<id>`.",
])

BLOCK_R_AUTHOR_014 = "\n".join([
    "- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) uses YAML flow style, such as `owners: [a, b]`, never block style (`- a` lines), which the frontmatter reader does not read as a list.",
])

BLOCK_R_AUTHOR_015 = "\n".join([
    "- When the criterion depends on a precondition the target checks with `spec-linter`, the test calls `lint()` on the fixture first and asserts zero hard failures before exercising the behavior under test. The call is exactly `lint(None, repo_root)`: `paths` first and positionally `None`, never one positional argument. Every requirement, guarantee and acceptance file the fixture writes starts with its `# <id>` heading line, then a blank line: a file without it fails lint. When the test spec gives the fixture as code, the test copies that code exactly instead of retyping the files.",
    "",
    "    import importlib.util",
    "    import sys",
    "    from pathlib import Path",
    "    import @MODULE@",
    "",
    "    gen = next(p for p in Path(@MODULE@.__file__).resolve().parents if p.name == \"gen\")",
    "    base = gen / \"spec-linter\"",
    "    path = base / \"spec_linter.py\" if (base / \"spec_linter.py\").is_file() else base / \"spec_linter\" / \"__init__.py\"",
    "    spec = importlib.util.spec_from_file_location(\"spec_linter\", path)",
    "    spec_linter = importlib.util.module_from_spec(spec)",
    "    sys.modules[\"spec_linter\"] = spec_linter",
    "    spec.loader.exec_module(spec_linter)",
    "    assert spec_linter.lint(None, repo_root).hard_failures == 0",
])

BLOCK_R_AUTHOR_021 = "\n".join([
    "Every field read from a value the target itself returns, not only a faked dependency's data, MUST use dual dict-or-attribute access, never one assumed shape:",
    "",
    "    def field(value, name):",
    "        return value[name] if isinstance(value, dict) else getattr(value, name)",
])

BLOCK_R_AUTHOR_022 = "\n".join([
    "A test MUST NEVER assert a fake was used by reaching into `sys.modules` under a guessed key: real loaders key modules dynamically, often by `repo_root` or a hash, so any guess is unreliable.",
])

BLOCK_R_AUTHOR_023 = "\n".join([
    "A test asserting that a wall-clock \"own write time\" field falls within a `[before, after]` window truncates `before` and `after` to the precision of the field's documented format, such as whole seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits (`datetime.now(timezone.utc).replace(microsecond=0)`), never comparing a timestamp truncated on write against microsecond-precision bounds.",
])

BLOCK_R_AUTHOR_024 = "\n".join([
    "To confirm a fake ran, the fake's own code appends one line per call to a log file at a path the test controls, and the test reads that file; never an in-process, module-level list, since the test cannot reliably find the module object that wrote it.",
    "A test builds the source of any file it writes by concatenating strings, with `repr()` for every value it embeds, never with `str.format`, `%` or an f-string over text that holds braces or percent signs.",
])

_BLOCKS = (
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


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _bundle_get(bundle, name, default):
    if isinstance(bundle, Mapping):
        value = bundle.get(name)
    else:
        value = getattr(bundle, name, None)
    return default if value is None else value


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_dependency(repo_root, slug, module_name):
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
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _reply_instruction(nonce):
    return (
        "Reply with the complete test file wrapped exactly as:\n\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----\n\n"
        "with each marker on a line of its own. Anything outside the markers is discarded."
    )


def _build_prompt(bundle, modules):
    module = modules[0]
    parts = [
        "You are writing one pytest test file for one acceptance criterion of a "
        "spec-driven component, from the spec text below alone, never from the "
        "component's implementation.",
        "You have no tool or file access: answer from this bundle alone.",
        "## Component\n\n" + _bundle_get(bundle, "component_id", ""),
        "## Criterion " + _bundle_get(bundle, "criterion_id", "") + "\n\n"
        + "Covers: " + _bundle_get(bundle, "covers", "") + "\n\n"
        + _bundle_get(bundle, "criterion_text", ""),
        "## Covered requirement\n\n" + _bundle_get(bundle, "requirement_text", ""),
        "## Interface\n\n" + _bundle_get(bundle, "interface", ""),
        "## Glossary\n\n" + _bundle_get(bundle, "glossary", ""),
        "## Dependency interfaces",
    ]
    for dep_id, text in _bundle_get(bundle, "dependency_interfaces", {}).items():
        parts.append("### " + dep_id + "\n\n" + text)
    testing = _bundle_get(bundle, "testing", "")
    if testing:
        parts.append("## Test spec\n\n" + testing)
    parts.append(
        "## Module under test\n\n"
        "Import the module under test with exactly this statement:\n\n"
        + "\n".join("import " + name for name in modules)
        + "\n\nThe generator may lay a module out as `<module>.py` or a `<module>/` "
        "package; the import is the same either way."
    )
    parts.append("## Rules")
    for block in _BLOCKS:
        parts.append(block.replace("@MODULE@", module))
    parts.append(
        "Write the test so it exercises the component's public interface as "
        "described and asserts the criterion's Then clause."
    )
    return "\n\n".join(parts)


def _extract(text, nonce):
    pattern = (
        re.escape("-----BEGIN FILE " + nonce + "-----") + "\n(.*?)\n"
        + re.escape("-----END FILE " + nonce + "-----")
    )
    match = re.search(pattern, text or "", re.DOTALL)
    return None if match is None else match.group(1)


def _criterion_hash(bundle):
    payload = json.dumps(
        {k: _bundle_get(bundle, k, "") for k in
         ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _with_header(bundle, content):
    first, _, rest = content.partition("\n")
    if first.startswith(_HEADER_PREFIX):
        content = rest
    return "# hotdocs-criterion: sha256:" + _criterion_hash(bundle) + "\n" + content


def _error(response_error):
    return {
        "category": _field(response_error, "category"),
        "message": _field(response_error, "message"),
    }


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path.cwd() if repo_root is None else Path(repo_root)
    component_id = _bundle_get(bundle, "component_id", "")
    criterion_id = _bundle_get(bundle, "criterion_id", "")
    slug = _slug(component_id)
    module_names = list(_bundle_get(bundle, "module_names", []))
    modules = module_names or [slug.replace("-", "_")]
    probe_module = module_names or slug.replace("-", "_")
    drivers = re.findall(
        r"^## Test driver: (.+)$", _bundle_get(bundle, "testing", ""), re.MULTILINE
    )

    def result(file, error, attempts, findings):
        return TestAuthoringResult(
            component_id=component_id,
            criterion_id=criterion_id,
            model=model,
            seed=seed,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            file=file,
            model_call_error=error,
            repair_attempts=attempts,
            probe_findings=findings,
        )

    llm_endpoint = _load_dependency(repo_root, "llm-endpoint", "llm_endpoint")
    test_probe = _load_dependency(repo_root, "test-probe", "test_probe")

    base_prompt = _build_prompt(bundle, modules)

    def call(prompt_body):
        nonce = secrets.token_hex(16)
        response = llm_endpoint.complete(
            prompt_body + "\n\n" + _reply_instruction(nonce), model, backend=llm_backend
        )
        response_error = _field(response, "model_call_error")
        if response_error:
            return None, _error(response_error)
        content = _extract(_field(response, "text"), nonce)
        if content is None:
            return None, {
                "category": "missing_file_markers",
                "message": "model reply held no matching BEGIN/END FILE markers",
            }
        return content, None

    content, error = call(base_prompt)
    if error:
        return result(None, error, 0, [])

    attempts = 0
    while True:
        report = test_probe.probe(content, bundle, probe_module, drivers=drivers)
        findings = [dict(f) for f in (_field(report, "findings") or [])]
        if _field(report, "ok"):
            rel = (
                "verification/" + slug + "/generated-test/test_"
                + criterion_id.lower().replace("-", "_") + ".py"
            )
            text = _with_header(bundle, content)
            target = repo_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            return result({"path": rel, "content": text}, None, attempts, findings)
        if attempts == 2:
            return result(None, {
                "category": "test_probe_failed",
                "message": "authored test failed test-probe after 2 repair attempts",
            }, attempts, findings)
        attempts += 1
        lines = "\n".join(
            str(f.get("kind")) + " (line " + str(f.get("line")) + "): " + str(f.get("message"))
            for f in findings if f.get("severity") == "error"
        )
        repair_prompt = (
            base_prompt
            + "\n\n## Rejected test\n\n"
            + "Your previous test file was rejected by test-probe. Its full source:\n\n"
            + content
            + "\n\nError findings:\n"
            + lines
            + "\n\nReply with the complete corrected test file, not a fragment."
        )
        content, error = call(repair_prompt)
        if error:
            return result(None, error, attempts, findings)


def _usage_error(cause):
    print("usage error: " + cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    opts = {}
    positionals = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("--"):
            name, eq, value = token.partition("=")
            if name not in _VALUE_FLAGS:
                return _usage_error("unknown argument " + token)
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(name + " requires a value")
                i += 1
                value = argv[i]
            opts[name] = value
        else:
            positionals.append(token)
        i += 1

    if len(positionals) != 2:
        return _usage_error("expected <component-id> and <criterion-id>")
    if "--model" not in opts:
        return _usage_error("missing required --model")
    fmt = opts.get("--format", "text")
    if fmt not in ("json", "text"):
        return _usage_error("--format must be json or text")
    seed_text = opts.get("--seed", "0")
    if not re.fullmatch(r"-?[0-9]+", seed_text):
        return _usage_error("--seed must be an integer")

    component_id, criterion_id = positionals
    model = opts["--model"]
    seed = int(seed_text)
    repo_root = Path(opts["--repo-root"]) if "--repo-root" in opts else Path.cwd()

    assembler = _load_dependency(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    result = author_test(bundle, model, seed, repo_root=repo_root)

    error = _field(result, "model_call_error")
    if fmt == "json":
        data = result if isinstance(result, dict) else dataclasses.asdict(result)
        print(json.dumps(data))
    elif error is None:
        print(criterion_id + ": wrote " + str(_field(_field(result, "file"), "path")))
    else:
        print(
            criterion_id + ": model_call_error " + str(_field(error, "category"))
            + ": " + str(_field(error, "message"))
        )
    return 0 if error is None else 1
