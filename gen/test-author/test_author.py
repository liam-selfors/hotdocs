"""test-author: authors the test code for one generated-test criterion."""

import dataclasses
import hashlib
import importlib.util
import json
import re
import secrets
import sys
from pathlib import Path

GATE_VERSION = "generated_test@3.0.0"
PROMPT_VERSION = "v1"

USAGE = (
    "usage: hotdocs author-test <component-id> <criterion-id> --model=<model-id> "
    "[--seed=<n>] [--repo-root=<dir>] [--format=json|text]"
)

HEADER_PREFIX = "# hotdocs-criterion:"

_HASH_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")


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


_BLOCKS = [
    """The component under test itself needs no custom loader: a plain `import @MODULE@`.
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
        return module""",
    """Any fake a test writes for a dependency's behavior MUST match that dependency's real, documented call signature and return shape exactly, as its interface above gives them, never invented or simplified.
Given a documented return type with named fields, a fake MUST return every field, never a bare list, string or number in its place, even when the test reads only one field. For a dependency that documents

    bar_get(key: str) -> Entry
    Entry: {"key": str, "value": str, "stored_at": str}

a correct fake is

    def bar_get(key):
        return {"key": key, "value": "v", "stored_at": "2026-01-01T00:00:00Z"}

and a fake whose body is `return "v"` is wrong.""",
    """When a test builds a synthetic spec corpus (a fixture) under a temporary `repo_root`:
- Every frontmatter-bearing document it builds (`component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) carries `id`, `title`, `status` and `owners`, always, with `status` exactly one of `draft`, `ratified` or `deprecated`.
- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`.
- Every `requirements/` file of every fixture component has a matching `acceptance/` file with a `Covers:` tag.
- A unit file (`constraints.md`, or anything under `requirements/`, `interface/` or `acceptance/`) carries no frontmatter at all.
- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text.""",
    """- A fixture component defaults to `sealed: true` with a short, fake `source_path` not under `gen/`, such as `source_path: legacy/foo/`, unless the criterion concerns `realizes` or capability linkage: sealed exempts it from `realizes` and the capability machinery.
- Only a criterion that needs `realizes`-driven behavior has the fixture supply a resolvable `P-<id>`.""",
    """- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) uses YAML flow style, such as `owners: [a, b]`, never block style (`- a` lines), which the frontmatter reader does not read as a list.""",
    """- When the criterion depends on a precondition the target checks with `spec-linter`, the test calls `lint()` on the fixture first and asserts zero hard failures before exercising the behavior under test. The call is exactly `lint(None, repo_root)`: `paths` first and positionally `None`, never one positional argument. Every requirement, guarantee and acceptance file the fixture writes starts with its `# <id>` heading line, then a blank line: a file without it fails lint. When the test spec gives the fixture as code, the test copies that code exactly instead of retyping the files.

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
    assert spec_linter.lint(None, repo_root).hard_failures == 0""",
    """Every field read from a value the target itself returns, not only a faked dependency's data, MUST use dual dict-or-attribute access, never one assumed shape:

    def field(value, name):
        return value[name] if isinstance(value, dict) else getattr(value, name)""",
    """A test MUST NEVER assert a fake was used by reaching into `sys.modules` under a guessed key: real loaders key modules dynamically, often by `repo_root` or a hash, so any guess is unreliable.""",
    """A test asserting that a wall-clock "own write time" field falls within a `[before, after]` window truncates `before` and `after` to the precision of the field's documented format, such as whole seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits (`datetime.now(timezone.utc).replace(microsecond=0)`), never comparing a timestamp truncated on write against microsecond-precision bounds.""",
    """To confirm a fake ran, the fake's own code appends one line per call to a log file at a path the test controls, and the test reads that file; never an in-process, module-level list, since the test cannot reliably find the module object that wrote it.
A test builds the source of any file it writes by concatenating strings, with `repr()` for every value it embeds, never with `str.format`, `%` or an f-string over text that holds braces or percent signs.""",
]


def _read(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _field(bundle, name, default):
    if isinstance(bundle, dict):
        value = bundle.get(name)
    else:
        value = getattr(bundle, name, None)
    return default if value is None else value


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_dependency(slug, module_name, repo_root):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    flat = base / (module_name + ".py")
    path = flat if flat.is_file() else base / module_name / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _slug(component_id):
    return component_id.removeprefix("comp-")


def _modules(bundle):
    names = list(_field(bundle, "module_names", []))
    if names:
        return names
    return [_slug(_field(bundle, "component_id", "")).replace("-", "_")]


def _criterion_hash(bundle):
    values = {key: _field(bundle, key, "") for key in _HASH_KEYS}
    text = json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reply_instruction(nonce):
    return (
        "## Reply format\n\n"
        "Wrap the complete test file's content exactly as follows, each marker on a line of its own:\n\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----"
    )


def _build_prompt(bundle, modules):
    component_id = _field(bundle, "component_id", "")
    parts = [
        "You are writing one pytest test file for one acceptance criterion of the component `"
        + component_id
        + "`, from its spec alone, never its implementation. "
        "You have no tool or file access: answer from this bundle alone.",
        "## Criterion " + _field(bundle, "criterion_id", "") + "\n\n"
        "Covers: " + _field(bundle, "covers", "") + "\n\n"
        + _field(bundle, "criterion_text", "")
        + "\n\nThe test MUST exercise the component's public interface and assert the criterion's Then clause.",
        "## Covered requirement\n\n" + _field(bundle, "requirement_text", ""),
        "## Interface of the component under test\n\n" + _field(bundle, "interface", ""),
        "## Glossary\n\n" + _field(bundle, "glossary", ""),
        "## Dependency interfaces",
    ]
    for dep_id, text in _field(bundle, "dependency_interfaces", {}).items():
        parts.append("### " + dep_id + "\n" + text)
    testing = _field(bundle, "testing", "")
    if testing:
        parts.append("## Test spec\n" + testing)
    parts.append(
        "## Module under test\n\nImport the module under test with exactly:\n\n"
        + "\n".join("import " + name for name in modules)
    )
    parts.append("## Rules")
    for block in _BLOCKS:
        parts.append(block.replace("@MODULE@", modules[0]))
    return "\n\n".join(parts)


def _extract(text, nonce):
    pattern = re.compile(
        "-----BEGIN FILE " + nonce + "-----\n(.*?)\n-----END FILE " + nonce + "-----",
        re.S,
    )
    match = pattern.search(text or "")
    return None if match is None else match.group(1)


def _error(response_error):
    return {
        "category": _read(response_error, "category"),
        "message": _read(response_error, "message"),
    }


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path.cwd() if repo_root is None else Path(repo_root)
    component_id = _field(bundle, "component_id", "")
    criterion_id = _field(bundle, "criterion_id", "")
    modules = _modules(bundle)
    probe_module = list(_field(bundle, "module_names", [])) or modules[0]

    llm_endpoint = _load_dependency("llm-endpoint", "llm_endpoint", repo_root)
    test_probe = _load_dependency("test-probe", "test_probe", repo_root)

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

    prompt = _build_prompt(bundle, modules)
    nonce = secrets.token_hex(16)
    original = prompt + "\n\n" + _reply_instruction(nonce)
    response = llm_endpoint.complete(original, model, backend=llm_backend)
    attempts = 0
    findings = []
    while True:
        response_error = _read(response, "model_call_error")
        if response_error:
            return result(None, _error(response_error), attempts, findings)
        content = _extract(_read(response, "text"), nonce)
        if content is None:
            return result(
                None,
                {
                    "category": "missing_file_markers",
                    "message": "reply holds no matching BEGIN/END FILE markers",
                },
                attempts,
                findings,
            )
        report = test_probe.probe(content, bundle, probe_module)
        findings = [dict(f) for f in _read(report, "findings")]
        if _read(report, "ok"):
            body = content
            if body.split("\n", 1)[0].startswith(HEADER_PREFIX):
                body = body.partition("\n")[2]
            full = "# hotdocs-criterion: sha256:" + _criterion_hash(bundle) + "\n" + body
            rel = (
                "verification/" + _slug(component_id) + "/generated-test/test_"
                + criterion_id.lower().replace("-", "_") + ".py"
            )
            target = repo_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(full.encode("utf-8"))
            return result({"path": rel, "content": full}, None, attempts, findings)
        if attempts == 2:
            return result(
                None,
                {
                    "category": "test_probe_failed",
                    "message": "authored test failed its probe after 2 repair attempts",
                },
                attempts,
                findings,
            )
        attempts += 1
        lines = [
            str(_read(f, "kind")) + " (line " + str(_read(f, "line")) + "): " + str(_read(f, "message"))
            for f in findings
            if _read(f, "severity") == "error"
        ]
        nonce = secrets.token_hex(16)
        repair = (
            original
            + "\n\n## Rejected test\n\n"
            "The test file below was rejected by its probe. Reply with the complete corrected test file.\n\n"
            + content
            + "\n\n## Probe findings\n\n"
            + "\n".join(lines)
            + "\n\n"
            + _reply_instruction(nonce)
        )
        response = llm_endpoint.complete(repair, model, backend=llm_backend)


_FLAGS = {"--model": "model", "--seed": "seed", "--repo-root": "repo_root", "--format": "format"}


def _usage_error(cause):
    print("usage error: " + cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    tokens = sys.argv[1:] if argv is None else list(argv)
    values = {}
    positional = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            name, eq, value = token.partition("=")
            if name not in _FLAGS:
                return _usage_error("unknown argument " + token)
            if not eq:
                if i + 1 == len(tokens):
                    return _usage_error(name + " requires a value")
                i += 1
                value = tokens[i]
            values[_FLAGS[name]] = value
        else:
            positional.append(token)
        i += 1
    if len(positional) != 2:
        return _usage_error("expected <component-id> and <criterion-id>")
    if "model" not in values:
        return _usage_error("missing required --model")
    fmt = values.get("format", "text")
    if fmt not in ("json", "text"):
        return _usage_error("--format must be json or text")
    seed_text = values.get("seed", "0")
    if not re.fullmatch(r"-?[0-9]+", seed_text):
        return _usage_error("--seed must be an integer")

    component_id, criterion_id = positional
    repo_root = Path(values["repo_root"]) if "repo_root" in values else Path.cwd()
    assembler = _load_dependency("spec-bundle-assembler", "spec_bundle_assembler", repo_root)
    bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    result = author_test(bundle, values["model"], int(seed_text), repo_root=repo_root)

    error = _read(result, "model_call_error")
    if fmt == "json":
        print(json.dumps(dataclasses.asdict(result)))
    elif error is None:
        print(criterion_id + ": wrote " + str(_read(_read(result, "file"), "path")))
    else:
        print(
            criterion_id + ": model_call_error " + str(_read(error, "category"))
            + ": " + str(_read(error, "message"))
        )
    return 0 if error is None else 1
