"""The single `hotdocs` command: routes `hotdocs <verb> ...` to its component."""

import contextlib
import hashlib
import importlib
import importlib.util
import io
import os
import sys
import tomllib
from pathlib import Path

# (verb words, dir, module, strip, model, summary)
VERB_TABLE = [
    (("lint",), "gen/spec-linter", "spec_linter", 1, "no", "validate the spec corpus"),
    (("impact",), "gen/impact-analyzer", "impact_analyzer", 1, "no", "blast radius of a change"),
    (("assemble",), "gen/spec-bundle-assembler", "spec_bundle_assembler", 1, "no",
     "build a component's spec bundle"),
    (("compile-criteria",), "pipeline/criterion-compiler", "criterion_compiler", 1, "no",
     "compile the compiled criteria"),
    (("author-test",), "gen/test-author", "test_author", 0, "required",
     "write one criterion's test"),
    (("verify-component",), "gen/verifier-orchestrator", "verifier_orchestrator", 1, "no",
     "verify one component"),
    (("generate",), "gen/component-gate-runner", "component_gate_runner", 0, "required",
     "generate and verify a component"),
    (("verify",), "gen/provenance-tracker", "provenance_tracker", 0, "optional",
     "is everything ready"),
    (("track", "feedback"), "gen/provenance-tracker", "provenance_tracker", 0, "no",
     "last failing requirements"),
    (("track", "ui", "build"), "gen/provenance-tracker-ui", "provenance_tracker_ui", 0, "optional",
     "build the readiness page"),
    (("provenance", "check"), "gen/provenance-checker", "provenance_checker", 1, "no",
     "is provenance a hit"),
    (("provenance", "write"), "gen/provenance-writer", "provenance_writer", 0, "no",
     "write a provenance manifest"),
    (("license-scan",), "gen/license-scanner", "license_scanner", 1, "no",
     "license scan one component"),
    (("secret-scan",), "gen/secret-scanner", "secret_scanner", 1, "no", "scan for secrets"),
    (("review-packet", "build"), "gen/review-packet-builder", "review_packet_builder", 0, "no",
     "build a review packet"),
    (("decision-drift",), "gen/decision-drift-detector", "decision_drift_detector", 0, "no",
     "decisions out of step with specs"),
    (("decision-impact",), "gen/decision-drift-detector", "decision_drift_detector", 0, "no",
     "what a decision touches"),
    (("docs-site", "build"), "gen/docs-site-renderer", "docs_site_renderer.cli", 2, "no",
     "render the docs site"),
    (("corpus-graph", "build"), "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1, "no",
     "build the corpus graph"),
    (("assist",), "gen/spec-completeness-assistant", "spec_completeness_assistant", 1, "optional",
     "review a spec change"),
    (("spec", "check"), "gen/spec-reviewer", "spec_reviewer", 2, "optional",
     "check criteria from their test authors' view"),
    (("decision", "new"), "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "draft the next decision record"),
    (("decision", "ratify"), "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "ratify a decision record"),
    (("decision", "record-commit"), "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "record the commit that landed a decision"),
    (("component", "new"), "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "lay out a new component"),
    (("kind", "new"), "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "scaffold a new asset kind"),
    (("capability", "new"), "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "lay out a new capability"),
    (("init",), "gen/hotdocs-init", "hotdocs_init", 1, "no", "set up a new project"),
]

USAGE = "usage: hotdocs <verb words> [args...]"
CONFIG_VAR = "VAR_HOTDOCS_CONFIG"
LLM_DIR = "gen/llm-endpoint"
LLM_MODULE = "llm_endpoint"


def _default_tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _tool_version(tool_root):
    try:
        with open(os.path.join(os.fspath(tool_root), "pyproject.toml"), "rb") as handle:
            data = tomllib.load(handle)
        version = data["project"]["version"]
    except Exception:
        return "unknown"
    if isinstance(version, str) and version:
        return version
    return "unknown"


def _verb_lines():
    names = [" ".join(row[0]) for row in VERB_TABLE]
    width = max(len(name) for name in names)
    return [f"  {name.ljust(width)}  {row[5]}" for name, row in zip(names, VERB_TABLE)]


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _module_file(base, dir_, module):
    """Return the module's file under base, or None when absent."""
    stem = os.path.join(os.fspath(base), dir_, *module.split("."))
    if os.path.isfile(stem + ".py"):
        return stem + ".py"
    package_init = os.path.join(stem, "__init__.py")
    if os.path.isfile(package_init):
        return package_init
    return None


def _choose_base(repo_root, tool_root, dir_):
    if os.path.isdir(os.path.join(os.fspath(repo_root), dir_)):
        return repo_root
    return tool_root


@contextlib.contextmanager
def _loaded(base, dir_, module, path, key_root):
    if "." in module:
        root = os.path.join(os.fspath(base), dir_)
        package = module.split(".")[0]

        def purge():
            for name in list(sys.modules):
                if name == package or name.startswith(package + "."):
                    del sys.modules[name]

        purge()
        sys.path.insert(0, root)
        importlib.invalidate_caches()
        try:
            yield importlib.import_module(module)
        finally:
            if root in sys.path:
                sys.path.remove(root)
            purge()
        return
    digest = hashlib.sha1(os.fspath(key_root).encode("utf-8")).hexdigest()[:16]
    name = f"_hotdocs_cli_{digest}_{module}"
    locations = None
    if os.path.basename(path) == "__init__.py":
        locations = [os.path.dirname(path)]
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=locations
    )
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    try:
        with open(path, "rb") as handle:
            source = handle.read()
        exec(compile(source, path, "exec"), loaded.__dict__)
        yield loaded
    finally:
        sys.modules.pop(name, None)


def _call(fn, args, kwargs):
    try:
        code = fn(args, **kwargs)
    except SystemExit as exit_:
        code = exit_.code
        if code is None:
            return 0
        if not isinstance(code, int):
            return 1
        return code
    except Exception as error:
        if type(error).__name__ == "ModelResolutionError":
            print(f"usage error: {error}", file=sys.stderr)
            return 2
        raise
    if code is None:
        return 0
    return code


def _repo_root_arg(rest):
    for index, token in enumerate(rest):
        if token.startswith("--repo-root="):
            return token[len("--repo-root="):]
        if token == "--repo-root" and index + 1 < len(rest):
            return rest[index + 1]
    return None


def _inject_model(row, rest, forwarded, repo_root, tool_root):
    if "--no-model" in rest:
        return [token for token in forwarded if token != "--no-model"]
    if any(token == "--model" or token.startswith("--model=") for token in rest):
        return forwarded
    base = _choose_base(repo_root, tool_root, LLM_DIR)
    path = _module_file(base, LLM_DIR, LLM_MODULE)
    if path is None:
        return forwarded
    with _loaded(base, LLM_DIR, LLM_MODULE, path, repo_root) as endpoint:
        try:
            config = endpoint.load_config(Path(repo_root) / "hotdocs.toml")
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return forwarded
    if config is None:
        return forwarded
    provider = _get(config, "provider")
    model = _get(config, "model")
    if not provider or not model:
        return forwarded
    model_string = f"{provider}:{model}"
    if row[4] == "optional":
        print(
            f"hotdocs: using model {model_string} from hotdocs.toml (pass --no-model to skip)",
            file=sys.stderr,
        )
    return forwarded + [f"--model={model_string}"]


def run(argv=None, *, tool_root=None, input_fn=None, output_fn=None, env=None, cwd=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if tool_root is None:
        tool_root = _default_tool_root()
    if input_fn is None:
        input_fn = input
    if output_fn is None:
        output_fn = print
    if env is None:
        env = os.environ
    if cwd is None:
        cwd = os.getcwd()

    if not argv or argv[0] in ("help", "--help", "-h"):
        output_fn(f"hotdocs {_tool_version(tool_root)}")
        output_fn(USAGE)
        for line in _verb_lines():
            output_fn(line)
        return 0
    if argv[0] == "--version":
        output_fn(f"hotdocs {_tool_version(tool_root)}")
        return 0

    row = None
    for candidate in VERB_TABLE:
        words = list(candidate[0])
        if argv[: len(words)] == words and (row is None or len(words) > len(row[0])):
            row = candidate
    if row is None:
        print(f"usage error: unknown verb: {argv[0]}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        for line in _verb_lines():
            print(line, file=sys.stderr)
        return 2

    words, dir_, module, strip, model_kind, summary = row
    verb = " ".join(words)
    rest = argv[len(words):]
    forwarded = argv[strip:]
    help_mode = "--help" in rest or "-h" in rest
    is_init = words == ("init",)

    if is_init:
        repo_root = tool_root
        base = tool_root
    else:
        value = _repo_root_arg(rest)
        cwd_abs = os.path.abspath(os.fspath(cwd))
        if value is None:
            repo_root = cwd_abs
            forwarded = forwarded + [f"--repo-root={repo_root}"]
        else:
            repo_root = os.path.abspath(os.path.join(cwd_abs, value))
        base = _choose_base(repo_root, tool_root, dir_)

    path = _module_file(base, dir_, module)
    if path is None:
        missing = os.path.join(os.fspath(tool_root), dir_, *module.split(".")) + ".py"
        print(f"hotdocs: {verb}: component not found: {missing}", file=sys.stderr)
        return 2

    if not is_init and not help_mode and model_kind in ("required", "optional"):
        forwarded = _inject_model(row, rest, forwarded, repo_root, tool_root)

    set_config = False
    if not is_init:
        config_file = os.path.join(repo_root, "hotdocs.toml")
        if os.path.isfile(config_file) and not os.environ.get(CONFIG_VAR):
            previous = os.environ.get(CONFIG_VAR)
            os.environ[CONFIG_VAR] = config_file
            set_config = True

    captured = io.StringIO()
    try:
        with _loaded(base, dir_, module, path, repo_root) as component:
            entry_name = "run" if is_init else "main"
            entry = getattr(component, entry_name, None)
            if entry is None:
                print(f"hotdocs: {verb}: {entry_name} is not available", file=sys.stderr)
                return 2
            kwargs = {}
            if is_init:
                kwargs = {
                    "tool_root": tool_root,
                    "input_fn": input_fn,
                    "output_fn": output_fn,
                    "env": env,
                    "cwd": cwd,
                }
            if help_mode:
                with contextlib.redirect_stderr(captured):
                    code = _call(entry, forwarded, kwargs)
            else:
                code = _call(entry, forwarded, kwargs)
    finally:
        if set_config:
            if previous is None:
                os.environ.pop(CONFIG_VAR, None)
            else:
                os.environ[CONFIG_VAR] = previous

    if help_mode:
        text = captured.getvalue()
        lines = text.splitlines()
        if code == 2 and lines and lines[0].startswith("usage error:"):
            output_fn(f"hotdocs {verb}: {summary}")
            for line in lines[1:]:
                if line.strip():
                    output_fn(line)
            return 0
        sys.stderr.write(text)
    return code


def main(argv=None):
    return run(argv)
