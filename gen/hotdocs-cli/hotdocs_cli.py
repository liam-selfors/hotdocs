"""The single `hotdocs` command: routes `hotdocs <verb> ...` to its component."""

import contextlib
import hashlib
import importlib
import importlib.util
import os
import sys
from pathlib import Path

TOOL_VERSION = "0.1.0"

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
    (("verify",), "gen/provenance-tracker", "provenance_tracker", 0, "no", "is everything ready"),
    (("track", "feedback"), "gen/provenance-tracker", "provenance_tracker", 0, "no",
     "last failing requirements"),
    (("track", "ui", "build"), "gen/provenance-tracker-ui", "provenance_tracker_ui", 0, "no",
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
    (("assist",), "gen/spec-completeness-assistant", "spec_completeness_assistant", 1, "no",
     "review a spec change"),
    (("init",), "gen/hotdocs-init", "hotdocs_init", 1, "no", "set up a new project"),
]

_LLM_DIR = "gen/llm-endpoint"
_LLM_MODULE = "llm_endpoint"
_CONFIG_VAR = "VAR_HOTDOCS_CONFIG"


def _default_tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _verb_lines():
    return ["  %-22s %s" % (" ".join(row[0]), row[5]) for row in VERB_TABLE]


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _module_file(base, module):
    rel = module.replace(".", "/")
    flat = Path(base) / (rel + ".py")
    if flat.is_file():
        return flat
    pkg = Path(base) / rel / "__init__.py"
    if pkg.is_file():
        return pkg
    return None


def _base(repo_root, tool_root, dir_):
    candidate = Path(repo_root) / dir_
    if candidate.is_dir():
        return candidate
    return Path(tool_root) / dir_


def _purge(name):
    for key in list(sys.modules):
        if key == name or key.startswith(name + "."):
            del sys.modules[key]


@contextlib.contextmanager
def _loaded(base, module, path):
    if "." in module:
        pkg = module.split(".")[0]
        _purge(pkg)
        sys.path.insert(0, str(base))
        try:
            importlib.invalidate_caches()
            yield importlib.import_module(module)
        finally:
            sys.path.remove(str(base))
            _purge(pkg)
    else:
        digest = hashlib.sha256(str(base).encode("utf-8")).hexdigest()[:16]
        name = "_hotdocs_%s_%s" % (digest, module)
        locations = [str(path.parent)] if path.name == "__init__.py" else None
        spec = importlib.util.spec_from_file_location(
            name, str(path), submodule_search_locations=locations
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
            yield mod
        finally:
            _purge(name)


def _repo_root_arg(args):
    for i, tok in enumerate(args):
        if tok.startswith("--repo-root="):
            return tok[len("--repo-root="):]
        if tok == "--repo-root" and i + 1 < len(args):
            return args[i + 1]
    return None


def _configured_model(repo_root, tool_root):
    base = _base(repo_root, tool_root, _LLM_DIR)
    path = _module_file(base, _LLM_MODULE)
    if path is None:
        return None
    with _loaded(base, _LLM_MODULE, path) as llm:
        try:
            config = llm.load_config(Path(repo_root) / "hotdocs.toml")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return None
    provider = _get(config, "provider")
    model = _get(config, "model")
    if provider and model:
        return "%s:%s" % (provider, model)
    return None


def _invoke(mod, row, tokens, kwargs):
    entry = getattr(mod, "main", None)
    if entry is None:
        print("hotdocs: %s is not available" % " ".join(row[0]), file=sys.stderr)
        return 2
    try:
        rc = entry(tokens, **kwargs)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    except Exception as exc:
        if type(exc).__name__ == "ModelResolutionError":
            print("usage error: %s" % exc, file=sys.stderr)
            return 2
        raise
    if rc is None:
        return 0
    return rc


def _run(base, row, tokens, kwargs, tool_root):
    words, dir_, module = row[0], row[1], row[2]
    path = _module_file(base, module)
    if path is None:
        missing = Path(tool_root) / dir_ / (module.replace(".", "/") + ".py")
        print("hotdocs: %s: component not found at %s" % (" ".join(words), missing),
              file=sys.stderr)
        return 2
    with _loaded(base, module, path) as mod:
        return _invoke(mod, row, tokens, kwargs)


def main(argv=None, *, tool_root=None, input_fn=None, output_fn=None,
         env=None, cwd=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if input_fn is None:
        input_fn = input
    if output_fn is None:
        output_fn = print
    if env is None:
        env = os.environ
    if cwd is None:
        cwd = os.getcwd()
    if tool_root is None:
        tool_root = _default_tool_root()

    if not argv or argv[0] in ("help", "--help", "-h"):
        output_fn("hotdocs %s" % TOOL_VERSION)
        output_fn("usage: hotdocs <verb> [args...]")
        for line in _verb_lines():
            output_fn(line)
        return 0
    if argv[0] == "--version":
        output_fn("hotdocs %s" % TOOL_VERSION)
        return 0

    row = None
    for candidate in VERB_TABLE:
        words = list(candidate[0])
        if argv[:len(words)] == words and (row is None or len(words) > len(row[0])):
            row = candidate
    if row is None:
        print("unknown verb: %s" % argv[0], file=sys.stderr)
        for line in _verb_lines():
            print(line, file=sys.stderr)
        return 2

    words, dir_, module, strip, model = row[0], row[1], row[2], row[3], row[4]
    tokens = argv[strip:]

    if words == ("init",):
        kwargs = {
            "tool_root": tool_root,
            "input_fn": input_fn,
            "output_fn": output_fn,
            "env": env,
            "cwd": cwd,
        }
        return _run(Path(tool_root) / dir_, row, tokens, kwargs, tool_root)

    args = argv[len(words):]
    given = _repo_root_arg(args)
    if given is None:
        repo_root = os.path.abspath(str(cwd))
        tokens = tokens + ["--repo-root=%s" % repo_root]
    else:
        repo_root = os.path.abspath(os.path.join(str(cwd), given))

    if model == "required" and not any(
        t == "--model" or t.startswith("--model=") for t in args
    ):
        injected = _configured_model(repo_root, tool_root)
        if injected is not None:
            tokens = tokens + ["--model=%s" % injected]

    config_file = Path(repo_root) / "hotdocs.toml"
    previous = os.environ.get(_CONFIG_VAR)
    set_var = config_file.is_file() and not previous
    if set_var:
        os.environ[_CONFIG_VAR] = str(config_file)
    try:
        return _run(_base(repo_root, tool_root, dir_), row, tokens, {}, tool_root)
    finally:
        if set_var:
            if previous is None:
                os.environ.pop(_CONFIG_VAR, None)
            else:
                os.environ[_CONFIG_VAR] = previous
