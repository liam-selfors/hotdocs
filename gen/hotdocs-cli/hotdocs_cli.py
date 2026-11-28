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

# (verb words, dir, module, strip, model, summary) -- interface/data/VerbTable.md
VERB_TABLE = [
    ("lint", "gen/spec-linter", "spec_linter", 1, "no", "validate the spec corpus"),
    ("impact", "gen/impact-analyzer", "impact_analyzer", 1, "no", "blast radius of a change"),
    ("assemble", "gen/spec-bundle-assembler", "spec_bundle_assembler", 1, "no",
     "build a component's spec bundle"),
    ("compile-criteria", "pipeline/criterion-compiler", "criterion_compiler", 1, "no",
     "compile the compiled criteria"),
    ("author-test", "gen/test-author", "test_author", 1, "required",
     "write one criterion's test"),
    ("verify-component", "gen/verifier-orchestrator", "verifier_orchestrator", 1, "no",
     "verify one component"),
    ("generate", "gen/component-gate-runner", "component_gate_runner", 0, "required",
     "generate and verify a component"),
    ("verify", "gen/provenance-tracker", "provenance_tracker", 0, "optional",
     "is everything ready"),
    ("track feedback", "gen/provenance-tracker", "provenance_tracker", 0, "no",
     "last failing requirements"),
    ("track ui build", "gen/provenance-tracker-ui", "provenance_tracker_ui", 0, "optional",
     "build the readiness page"),
    ("provenance check", "gen/provenance-checker", "provenance_checker", 1, "no",
     "is provenance a hit"),
    ("provenance write", "gen/provenance-writer", "provenance_writer", 0, "no",
     "write a provenance manifest"),
    ("license-scan", "gen/license-scanner", "license_scanner", 1, "no",
     "license scan one component"),
    ("secret-scan", "gen/secret-scanner", "secret_scanner", 1, "no", "scan for secrets"),
    ("review-packet build", "gen/review-packet-builder", "review_packet_builder", 0, "no",
     "build a review packet"),
    ("decision-drift", "gen/decision-drift-detector", "decision_drift_detector", 0, "no",
     "decisions out of step with specs"),
    ("decision-impact", "gen/decision-drift-detector", "decision_drift_detector", 0, "no",
     "what a decision touches"),
    ("docs-site build", "gen/docs-site-renderer", "docs_site_renderer.cli", 2, "no",
     "render the docs site"),
    ("corpus-graph build", "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1, "no",
     "build the corpus graph"),
    ("assist", "gen/spec-completeness-assistant", "spec_completeness_assistant", 1,
     "optional", "review a spec change"),
    ("spec check", "gen/spec-reviewer", "spec_reviewer", 2, "optional",
     "check criteria from their test authors' view"),
    ("decision new", "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "draft the next decision record"),
    ("decision ratify", "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "ratify a decision record"),
    ("decision record-commit", "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "record the commit that landed a decision"),
    ("component new", "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "lay out a new component"),
    ("kind new", "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "scaffold a new asset kind"),
    ("capability new", "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "lay out a new capability"),
    ("init", "gen/hotdocs-init", "hotdocs_init", 1, "no", "set up a new project"),
]

USAGE = "usage: hotdocs <verb words> [args...] | hotdocs [--help | -h | help | --version]"
CONFIG_VAR = "VAR_HOTDOCS_CONFIG"


def _default_tool_root():
    here = Path(__file__).resolve()
    return str(next(p.parent for p in here.parents if p.name == "gen"))


def _tool_version(tool_root):
    try:
        with open(Path(tool_root) / "pyproject.toml", "rb") as handle:
            data = tomllib.load(handle)
        version = data["project"]["version"]
        if isinstance(version, str) and version:
            return version
    except Exception:
        pass
    return "unknown"


def _verb_lines():
    return [f"  {words:<24} {summary}" for words, _d, _m, _s, _mo, summary in VERB_TABLE]


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _match(argv):
    best = None
    for row in VERB_TABLE:
        words = row[0].split()
        if argv[:len(words)] == words and (best is None or len(words) > len(best[0].split())):
            best = row
    return best


def _module_path(base, directory, module, check=True):
    parts = module.split(".")
    path = Path(base).joinpath(directory, *parts[:-1], parts[-1] + ".py")
    if not check or path.is_file():
        return path
    package = Path(base).joinpath(directory, *parts, "__init__.py")
    if package.is_file():
        return package
    return None


def _drop(name):
    for key in list(sys.modules):
        if key == name or key.startswith(name + "."):
            del sys.modules[key]


@contextlib.contextmanager
def _loaded(base, directory, module, path):
    if "." in module:
        package = module.split(".")[0]
        location = str(Path(base) / directory)
        _drop(package)
        sys.path.insert(0, location)
        try:
            importlib.invalidate_caches()
            yield importlib.import_module(module)
        finally:
            _drop(package)
            sys.path.remove(location)
    else:
        digest = hashlib.sha1(str(base).encode("utf-8")).hexdigest()[:16]
        name = f"_hotdocs_{module}_{digest}"
        if path.name == "__init__.py":
            spec = importlib.util.spec_from_file_location(
                name, str(path), submodule_search_locations=[str(path.parent)])
        else:
            spec = importlib.util.spec_from_file_location(name, str(path))
        loaded = importlib.util.module_from_spec(spec)
        _drop(name)
        sys.modules[name] = loaded
        try:
            spec.loader.exec_module(loaded)
            yield loaded
        finally:
            _drop(name)


def _exit_code(code):
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _invoke(fn, tokens, kwargs):
    try:
        code = fn(tokens, **kwargs)
    except SystemExit as exc:
        return _exit_code(exc.code)
    except Exception as exc:
        if type(exc).__name__ != "ModelResolutionError":
            raise
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    return 0 if code is None else code


def _repo_root_arg(args):
    for index, token in enumerate(args):
        if token.startswith("--repo-root="):
            return token[len("--repo-root="):]
        if token == "--repo-root" and index + 1 < len(args):
            return args[index + 1]
    return None


def _configured_model(root, tool_root):
    base = root if (Path(root) / "gen/llm-endpoint").is_dir() else tool_root
    path = Path(base) / "gen/llm-endpoint/llm_endpoint.py"
    with _loaded(base, "gen/llm-endpoint", "llm_endpoint", path) as llm:
        try:
            config = llm.load_config(Path(root) / "hotdocs.toml")
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return None
    provider = _get(config, "provider")
    model = _get(config, "model")
    if provider and model:
        return f"{provider}:{model}"
    return None


def run(argv=None, *, tool_root=None, input_fn=None, output_fn=None, env=None, cwd=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    input_fn = input if input_fn is None else input_fn
    output_fn = print if output_fn is None else output_fn
    env = os.environ if env is None else env
    cwd = os.getcwd() if cwd is None else cwd
    tool_root = _default_tool_root() if tool_root is None else tool_root
    tool = Path(tool_root)

    if not argv or argv[0] in ("help", "--help", "-h"):
        output_fn(f"hotdocs {_tool_version(tool)}")
        output_fn(USAGE)
        for line in _verb_lines():
            output_fn(line)
        return 0
    if argv[0] == "--version":
        output_fn(f"hotdocs {_tool_version(tool)}")
        return 0

    row = _match(argv)
    if row is None:
        print(f"usage error: unknown verb: {argv[0]}", file=sys.stderr)
        for line in _verb_lines():
            print(line, file=sys.stderr)
        return 2

    words, directory, module, strip, model, summary = row
    args = argv[len(words.split()):]
    forwarded = argv[strip:]
    help_mode = "--help" in args or "-h" in args
    is_init = words == "init"

    if is_init:
        root = str(tool)
        base = tool
        kwargs = {"tool_root": tool_root, "input_fn": input_fn, "output_fn": output_fn,
                  "env": env, "cwd": cwd}
    else:
        value = _repo_root_arg(args)
        if value is None:
            root = os.path.abspath(cwd)
            forwarded.append(f"--repo-root={root}")
        else:
            root = os.path.abspath(value)
        base = Path(root) if (Path(root) / directory).is_dir() else tool
        kwargs = {}

    path = _module_path(base, directory, module)
    if path is None:
        missing = _module_path(tool, directory, module, check=False)
        print(f"hotdocs: {words}: component not found: {missing}", file=sys.stderr)
        return 2

    if model in ("required", "optional") and not help_mode:
        if "--no-model" in args:
            forwarded = [token for token in forwarded if token != "--no-model"]
        elif not any(t == "--model" or t.startswith("--model=") for t in args):
            model_string = _configured_model(root, tool)
            if model_string is not None:
                forwarded.append(f"--model={model_string}")
                if model == "optional":
                    print(f"hotdocs: using model {model_string} from hotdocs.toml "
                          f"(pass --no-model to skip)", file=sys.stderr)

    config_file = Path(root) / "hotdocs.toml"
    set_var = not is_init and config_file.is_file() and CONFIG_VAR not in os.environ
    if set_var:
        os.environ[CONFIG_VAR] = str(config_file)
    try:
        with _loaded(base, directory, module, path) as loaded:
            fn = getattr(loaded, "run" if is_init else "main", None)
            if fn is None:
                print(f"hotdocs: {words}: not available", file=sys.stderr)
                return 2
            if not help_mode:
                return _invoke(fn, forwarded, kwargs)
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                code = _invoke(fn, forwarded, kwargs)
    finally:
        if set_var:
            os.environ.pop(CONFIG_VAR, None)

    text = buffer.getvalue()
    lines = text.splitlines()
    if code == 2 and lines and lines[0].startswith("usage error:"):
        output_fn(f"hotdocs {words}: {summary}")
        for line in lines[1:]:
            if line:
                output_fn(line)
        return 0
    sys.stderr.write(text)
    return code


def main(argv=None):
    return run(argv)
