"""The single `hotdocs` command: routes `hotdocs <verb> ...` to its component."""

import contextlib
import hashlib
import importlib
import importlib.util
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
    (("track", "ui", "build"), "gen/provenance-tracker-ui", "provenance_tracker_ui", 0,
     "optional", "build the readiness page"),
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
    (("assist",), "gen/spec-completeness-assistant", "spec_completeness_assistant", 1,
     "optional", "review a spec change"),
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
    (("init",), "gen/hotdocs-init", "hotdocs_init", 1, "no", "set up a new project"),
]

USAGE = "usage: hotdocs <verb> [args...] | hotdocs [--help | -h | help | --version]"
CONFIG_VAR = "VAR_HOTDOCS_CONFIG"


def _default_tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _tool_version(tool_root):
    try:
        with open(Path(tool_root) / "pyproject.toml", "rb") as handle:
            data = tomllib.load(handle)
    except (OSError, ValueError):
        return "unknown"
    project = data.get("project")
    if not isinstance(project, dict):
        return "unknown"
    version = project.get("version")
    if isinstance(version, str) and version:
        return version
    return "unknown"


def _verb_lines():
    width = max(len(" ".join(row[0])) for row in VERB_TABLE)
    return [f"  {' '.join(row[0]):<{width}}  {row[5]}" for row in VERB_TABLE]


def _get(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _base_for(repo_root, tool_root, dir_):
    if repo_root is not None and (Path(repo_root) / dir_).exists():
        return repo_root
    return tool_root


def _module_file(base, dir_, module):
    stem = Path(base, dir_, *module.split("."))
    path = Path(str(stem) + ".py")
    if path.is_file():
        return path
    init = stem / "__init__.py"
    if init.is_file():
        return init
    return None


def _purge(top):
    for name in list(sys.modules):
        if name == top or name.startswith(top + "."):
            del sys.modules[name]


@contextlib.contextmanager
def _loaded(base, dir_, module, path):
    if "." in module:
        top = module.split(".")[0]
        entry = str(Path(base) / dir_)
        _purge(top)
        sys.path.insert(0, entry)
        importlib.invalidate_caches()
        try:
            yield importlib.import_module(module)
        finally:
            _purge(top)
            if entry in sys.path:
                sys.path.remove(entry)
    else:
        digest = hashlib.sha256(str(Path(base)).encode("utf-8")).hexdigest()[:16]
        name = f"_hotdocs_cli_{digest}_{module}"
        if path.name == "__init__.py":
            spec = importlib.util.spec_from_file_location(
                name, path, submodule_search_locations=[str(path.parent)])
        else:
            spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
            yield mod
        finally:
            sys.modules.pop(name, None)


def _repo_root_arg(args):
    for index, token in enumerate(args):
        if token.startswith("--repo-root="):
            return token[len("--repo-root="):]
        if token == "--repo-root" and index + 1 < len(args):
            return args[index + 1]
    return None


def _configured_model(repo_root, tool_root):
    dir_ = "gen/llm-endpoint"
    base = _base_for(repo_root, tool_root, dir_)
    path = _module_file(base, dir_, "llm_endpoint")
    with _loaded(base, dir_, "llm_endpoint", path) as mod:
        config = mod.load_config(Path(repo_root) / "hotdocs.toml")
    provider = _get(config, "provider")
    model = _get(config, "model")
    if provider and model:
        return f"{provider}:{model}"
    return None


def _exit_code(value):
    if value is None:
        return 0
    return value


def _call(fn, tokens, kwargs):
    try:
        result = fn(tokens, **kwargs)
    except SystemExit as error:
        code = error.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    except Exception as error:
        if type(error).__name__ == "ModelResolutionError":
            print(f"usage error: {error}", file=sys.stderr)
            return 2
        raise
    return _exit_code(result)


def run(argv=None, *, tool_root=None, input_fn=None, output_fn=None, env=None, cwd=None):
    argv = list(sys.argv[1:] if argv is None else argv)
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

    matches = [row for row in VERB_TABLE if tuple(argv[:len(row[0])]) == row[0]]
    if not matches:
        print(f"usage error: unknown verb: {argv[0]}", file=sys.stderr)
        for line in _verb_lines():
            print(line, file=sys.stderr)
        return 2
    words, dir_, module, strip, model_kind, _summary = max(matches, key=lambda r: len(r[0]))
    verb = " ".join(words)
    args = argv[len(words):]
    tokens = argv[strip:]
    is_init = words == ("init",)
    fn_name = "run" if is_init else "main"

    if is_init:
        repo_root = None
        base = tool_root
    else:
        given = _repo_root_arg(args)
        if given is None:
            repo_root = os.path.abspath(cwd)
            tokens.append(f"--repo-root={repo_root}")
        else:
            repo_root = os.path.abspath(os.path.join(cwd, given))
        base = _base_for(repo_root, tool_root, dir_)

    path = _module_file(base, dir_, module)
    if path is None:
        missing = Path(tool_root, dir_, *module.split("."))
        print(f"hotdocs: component for '{verb}' not found: {missing}.py", file=sys.stderr)
        return 2

    saved = []
    if not is_init:
        config_path = Path(repo_root) / "hotdocs.toml"
        if config_path.exists():
            targets = [env] if env is os.environ else [env, os.environ]
            for mapping in targets:
                if CONFIG_VAR not in mapping:
                    mapping[CONFIG_VAR] = str(config_path)
                    saved.append(mapping)
    try:
        with _loaded(base, dir_, module, path) as mod:
            fn = getattr(mod, fn_name, None)
            if fn is None:
                print(f"hotdocs: '{verb}' is not available (no {fn_name} in {path})",
                      file=sys.stderr)
                return 2
            if model_kind in ("required", "optional"):
                if "--no-model" in args:
                    tokens = [t for t in tokens if t != "--no-model"]
                elif not any(t == "--model" or t.startswith("--model=") for t in args):
                    try:
                        model = _configured_model(repo_root, tool_root)
                    except ValueError as error:
                        print(str(error), file=sys.stderr)
                        model = None
                    if model is not None:
                        tokens.append(f"--model={model}")
                        if model_kind == "optional":
                            print(f"hotdocs: using model {model} from hotdocs.toml "
                                  f"(pass --no-model to skip)", file=sys.stderr)
            if is_init:
                kwargs = {"tool_root": tool_root, "input_fn": input_fn,
                          "output_fn": output_fn, "env": env, "cwd": cwd}
            else:
                kwargs = {}
            return _call(fn, tokens, kwargs)
    finally:
        for mapping in saved:
            mapping.pop(CONFIG_VAR, None)


def main(argv=None):
    return run(argv)
