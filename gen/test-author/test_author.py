"""test-author: authors one generated-test criterion's test file from spec prose alone."""

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
HASH_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
FINDING_KEYS = ("kind", "severity", "line", "message")


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


BLOCK_R_AUTHOR_010 = '''The component under test itself needs no custom loader: a plain `import @MODULE@`.
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
        return module'''

BLOCK_R_AUTHOR_011 = '''Any fake a test writes for a dependency's behavior MUST match that dependency's real, documented call signature and return shape exactly, as its interface above gives them, never invented or simplified.
Given a documented return type with named fields, a fake MUST return every field, never a bare list, string or number in its place, even when the test reads only one field. For a dependency that documents

    bar_get(key: str) -> Entry
    Entry: {"key": str, "value": str, "stored_at": str}

a correct fake is

    def bar_get(key):
        return {"key": key, "value": "v", "stored_at": "2026-01-01T00:00:00Z"}

and a fake whose body is `return "v"` is wrong.'''

BLOCK_R_AUTHOR_012 = '''When a test builds a synthetic spec corpus (a fixture) under a temporary `repo_root`:
- Every frontmatter-bearing document it builds (`component.md`, `specs/vars/VAR-*.md`, `specs/decisions/D<N>.md`) carries `id`, `title`, `status` and `owners`, always, with `status` exactly one of `draft`, `ratified` or `deprecated`.
- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`.
- Every `requirements/` file of every fixture component has a matching `acceptance/` file with a `Covers:` tag.
- A unit file (`constraints.md`, or anything under `requirements/`, `interface/` or `acceptance/`) carries no frontmatter at all.
- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text.'''

BLOCK_R_AUTHOR_013 = '''- A fixture component defaults to `sealed: true` with a short, fake `source_path` not under `gen/`, such as `source_path: legacy/foo/`, unless the criterion concerns `realizes` or capability linkage: sealed exempts it from `realizes` and the capability machinery.
- Only a criterion that needs `realizes`-driven behavior has the fixture supply a resolvable `P-<id>`.'''

BLOCK_R_AUTHOR_014 = '''- Every list-valued frontmatter field (`owners`, `depends_on`, `realizes`, `uses_var`) uses YAML flow style, such as `owners: [a, b]`, never block style (`- a` lines), which the frontmatter reader does not read as a list.'''

BLOCK_R_AUTHOR_015 = '''- When the criterion depends on a precondition the target checks with `spec-linter`, the test calls `lint()` on the fixture first and asserts zero hard failures before exercising the behavior under test. The call is exactly `lint(None, repo_root)`: `paths` first and positionally `None`, never one positional argument. Every requirement, guarantee and acceptance file the fixture writes starts with its `# <id>` heading line, then a blank line: a file without it fails lint. When the test spec gives the fixture as code, the test copies that code exactly instead of retyping the files.

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
    assert spec_linter.lint(None, repo_root).hard_failures == 0'''

BLOCK_R_AUTHOR_021 = '''Every field read from a value the target itself returns, not only a faked dependency's data, MUST use dual dict-or-attribute access, never one assumed shape:

    def field(value, name):
        return value[name] if isinstance(value, dict) else getattr(value, name)'''

BLOCK_R_AUTHOR_022 = '''A test MUST NEVER assert a fake was used by reaching into `sys.modules` under a guessed key: real loaders key modules dynamically, often by `repo_root` or a hash, so any guess is unreliable.'''

BLOCK_R_AUTHOR_023 = '''A test asserting that a wall-clock "own write time" field falls within a `[before, after]` window truncates `before` and `after` to the precision of the field's documented format, such as whole seconds for a `%Y-%m-%dT%H:%M:%SZ` example with no fractional digits (`datetime.now(timezone.utc).replace(microsecond=0)`), never comparing a timestamp truncated on write against microsecond-precision bounds.'''

BLOCK_R_AUTHOR_024 = '''To confirm a fake ran, the fake's own code appends one line per call to a log file at a path the test controls, and the test reads that file; never an in-process, module-level list, since the test cannot reliably find the module object that wrote it.
A test builds the source of any file it writes by concatenating strings, with `repr()` for every value it embeds, never with `str.format`, `%` or an f-string over text that holds braces or percent signs.'''

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


def _get(value, name, default=None):
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _tool_root():
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load_dependency(repo_root, slug, module):
    base = Path(repo_root) / "gen" / slug
    if not base.is_dir():
        base = _tool_root() / "gen" / slug
    path = base / (module + ".py")
    if not path.is_file():
        path = base / module / "__init__.py"
    name = "_hotdocs_dep_" + module + "_" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def _criterion_hash(bundle):
    payload = {k: _get(bundle, k, "") for k in HASH_KEYS}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reply_instruction(nonce):
    return (
        "## Reply format\n"
        "\n"
        "You have no tool or file access: answer from this bundle alone.\n"
        "Wrap your test file's content exactly as:\n"
        "\n"
        "-----BEGIN FILE " + nonce + "-----\n"
        "<the complete, exact test file content, verbatim>\n"
        "-----END FILE " + nonce + "-----\n"
        "\n"
        "The two marker lines use exactly this nonce, " + nonce + ", each on a line of its own. "
        "A test needing markers in a stand-in model's reply builds them from the nonce it reads "
        "when it runs, never from this one."
    )


def _prompt_body(bundle, imports):
    module = imports[0]
    dependency_interfaces = _get(bundle, "dependency_interfaces", {})
    testing = _get(bundle, "testing", "")
    parts = [
        "You are writing one pytest test file for one acceptance criterion, from the spec alone, "
        "never the implementation. The test exercises the component's public interface as "
        "described and asserts the criterion's Then clause.",
        "## Component\n\n" + str(_get(bundle, "component_id", "")),
        "## Criterion " + str(_get(bundle, "criterion_id", "")) + "\n\n"
        + str(_get(bundle, "criterion_text", "")),
        "Covers: " + str(_get(bundle, "covers", "")),
        "## Covered requirement\n\n" + str(_get(bundle, "requirement_text", "")),
        "## Interface\n\n" + str(_get(bundle, "interface", "")),
        "## Glossary\n\n" + str(_get(bundle, "glossary", "")),
        "## Dependency interfaces",
    ]
    for dep_id, text in dependency_interfaces.items():
        parts.append("### " + dep_id + "\n\n" + text)
    if testing:
        parts.append("## Test spec\n\n" + testing)
    parts.append(
        "## Module under test\n\n"
        "The test imports the module under test with exactly this statement:\n\n"
        + "\n".join("import " + name for name in imports)
    )
    parts.append("## Rules")
    for block in BLOCKS:
        parts.append(block.replace("@MODULE@", module))
    return "\n\n".join(parts)


def _extract(text, nonce):
    match = re.search(
        "-----BEGIN FILE " + nonce + "-----\n(.*?)\n-----END FILE " + nonce + "-----",
        text,
        re.S,
    )
    return match.group(1) if match else None


def _write(repo_root, slug, criterion_id, content, bundle):
    first, _, rest = content.partition("\n")
    body = rest if first.startswith(HEADER_PREFIX) else content
    file_content = HEADER_PREFIX + " sha256:" + _criterion_hash(bundle) + "\n" + body
    rel = (
        "verification/" + slug + "/generated-test/test_"
        + criterion_id.lower().replace("-", "_") + ".py"
    )
    target = Path(repo_root) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(file_content.encode("utf-8"))
    return {"path": rel, "content": file_content}


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    repo_root = Path.cwd() if repo_root is None else Path(repo_root)
    component_id = _get(bundle, "component_id", "")
    criterion_id = _get(bundle, "criterion_id", "")
    slug = component_id.removeprefix("comp-")
    module_names = _get(bundle, "module_names", [])
    derived = slug.replace("-", "_")
    module_name = list(module_names) if module_names else derived
    imports = list(module_names) if module_names else [derived]
    drivers = re.findall(r"^## Test driver: (.*)$", _get(bundle, "testing", ""), re.M)

    llm_endpoint = _load_dependency(repo_root, "llm-endpoint", "llm_endpoint")
    test_probe = _load_dependency(repo_root, "test-probe", "test_probe")

    body = _prompt_body(bundle, imports)
    nonce = secrets.token_hex(16)
    original = body + "\n\n" + _reply_instruction(nonce)
    prompt = original
    repair_attempts = 0
    probe_findings = []

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
            repair_attempts=repair_attempts,
            probe_findings=probe_findings,
        )

    while True:
        response = llm_endpoint.complete(prompt, model, backend=llm_backend)
        error = _get(response, "model_call_error")
        if error is not None:
            return result(None, {
                "category": _get(error, "category"),
                "message": _get(error, "message"),
            })
        text = _get(response, "text")
        content = _extract(text, nonce)
        if content is None:
            failure = {
                "category": "missing_file_markers",
                "message": "model reply held no matching BEGIN/END FILE markers; reply began: "
                + repr(text[:200]),
            }
            feedback = (
                "Your reply held no BEGIN FILE / END FILE marker pair with the nonce "
                + nonce + "."
            )
        else:
            report = test_probe.probe(content, bundle, module_name, drivers=drivers)
            probe_findings = [
                {k: _get(f, k) for k in FINDING_KEYS} for f in _get(report, "findings", [])
            ]
            if _get(report, "ok"):
                return result(_write(repo_root, slug, criterion_id, content, bundle), None)
            failure = {
                "category": "test_probe_failed",
                "message": "authored test failed test-probe after "
                + str(repair_attempts) + " repair attempts",
            }
            feedback = (
                "Your test failed its probe. Its full source:\n\n" + content
                + "\n\nIts error findings:\n"
                + "\n".join(
                    str(f["kind"]) + " (line " + str(f["line"]) + "): " + str(f["message"])
                    for f in probe_findings
                    if f["severity"] == "error"
                )
            )
        if repair_attempts == 2:
            return result(None, failure)
        repair_attempts += 1
        nonce = secrets.token_hex(16)
        prompt = (
            original + "\n\n" + feedback + "\n\n"
            "Reply with the complete corrected test file, in the same markers, "
            "with the fresh nonce below.\n\n" + _reply_instruction(nonce)
        )


def _usage_error(cause):
    print("usage error: " + cause, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    flags = {
        "--model": None,
        "--seed": "0",
        "--repo-root": str(Path.cwd()),
        "--format": "text",
    }
    positionals = []
    i = 0
    while i < len(argv):
        token = argv[i]
        name, eq, value = token.partition("=")
        if name in flags:
            if not eq:
                if i + 1 >= len(argv):
                    return _usage_error(name + " requires a value")
                i += 1
                value = argv[i]
            flags[name] = value
        elif token.startswith("-"):
            return _usage_error("unknown argument " + token)
        else:
            positionals.append(token)
        i += 1

    if len(positionals) != 2:
        return _usage_error("expected <component-id> and <criterion-id>")
    if flags["--model"] is None:
        return _usage_error("missing required --model")
    if flags["--format"] not in ("json", "text"):
        return _usage_error("--format must be json or text")
    if not re.fullmatch(r"-?[0-9]+", flags["--seed"]):
        return _usage_error("--seed must be an integer")

    component_id, criterion_id = positionals
    model = flags["--model"]
    seed = int(flags["--seed"])
    repo_root = Path(flags["--repo-root"])

    try:
        assembler = _load_dependency(repo_root, "spec-bundle-assembler", "spec_bundle_assembler")
        bundle = assembler.assemble_criterion(component_id, criterion_id, repo_root)
    except Exception as exc:
        print(criterion_id + ": cannot build its bundle: " + str(exc), file=sys.stderr)
        return 1

    result = author_test(bundle, model, seed, repo_root=repo_root)
    error = _get(result, "model_call_error")
    if flags["--format"] == "json":
        print(json.dumps(dataclasses.asdict(result)))
    elif error is None:
        print(criterion_id + ": wrote " + str(_get(_get(result, "file"), "path")))
    else:
        print(
            criterion_id + ": model_call_error " + str(_get(error, "category"))
            + ": " + str(_get(error, "message"))
        )
    return 0 if error is None else 1
