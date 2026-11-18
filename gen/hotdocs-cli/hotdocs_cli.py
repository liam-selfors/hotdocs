"""The single ``hotdocs`` command: routes ``hotdocs <verb> ...`` to the
component that implements the verb."""

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
    (("verify",), "gen/provenance-tracker", "provenance_tracker", 0, "no",
     "is everything ready"),
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
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _verb_lines():
    return ["  %-22s %s" % (" ".join(words), summary)
            for words, _d, _m, _s, _mo, summary in VERB_TABLE]


def _base(repo_root, tool_root, d):
    candidate = Path(repo_root) / d
    if candidate.is_dir():
        return candidate
    return Path(tool_root) / d


def _locate(base, module):
    parts = module.split(".")
    flat = base.joinpath(*parts[:-1], parts[-1] + ".py")
    if flat.is_file():
        return flat
    pkg = base.joinpath(*parts, "__init__.py")
    if pkg.is_file():
        return pkg
    return None


def _purge(pkg):
    for name in list(sys.modules):
        if name == pkg or name.startswith(pkg + "."):
            del sys.modules[name]


@contextlib.contextmanager
def _loaded(path, base, module):
    if "." in module:
        pkg = module.split(".")[0]
        entry = str(base)
        _purge(pkg)
        sys.path.insert(0, entry)
        importlib.invalidate_caches()
        try:
            yield importlib.import_module(module)
        finally:
            _purge(pkg)
            if entry in sys.path:
                sys.path.remove(entry)
    else:
        digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]
        name = "_hotdocs_%s_%s" % (digest, module)
        if path.name == "__init__.py":
            spec = importlib.util.spec_from_file_location(
                name, str(path), submodule_search_locations=[str(path.parent)])
        else:
            spec = importlib.util.spec_from_file_location(name, str(path))
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


def _has_model(args):
    return any(tok == "--model" or tok.startswith("--model=") for tok in args)


def _model_token(repo_root, tool_root):
    base = _base(repo_root, tool_root, _LLM_DIR)
    path = _locate(base, _LLM_MODULE)
    with _loaded(path, base, _LLM_MODULE) as ep:
        try:
            cfg = ep.load_config(Path(repo_root) / "hotdocs.toml")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return None
    provider = _get(cfg, "provider") if cfg is not None else None
    model = _get(cfg, "model") if cfg is not None else None
    if provider and model:
        return "--model=%s:%s" % (provider, model)
    return None


def _run(fn, args, kwargs):
    try:
        rc = fn(args, **kwargs)
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


def main(argv=None, *, tool_root=None, input_fn=None, output_fn=None,
         env=None, cwd=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if tool_root is None:
        tool_root = _default_tool_root()
    tool_root = Path(tool_root)
    if input_fn is None:
        input_fn = input
    if output_fn is None:
        output_fn = print
    if env is None:
        env = os.environ
    if cwd is None:
        cwd = os.getcwd()

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

    words, d, module, strip, model, _summary = row
    verb_name = " ".join(words)
    rest = argv[len(words):]
    tokens = argv[strip:]

    if words == ("init",):
        base = tool_root / d
        repo_root = None
    else:
        given = _repo_root_arg(rest)
        if given is None:
            repo_root = os.path.abspath(str(cwd))
            tokens = tokens + ["--repo-root=%s" % repo_root]
        else:
            repo_root = os.path.abspath(os.path.join(str(cwd), given))
        base = _base(repo_root, tool_root, d)

    path = _locate(base, module)
    if path is None:
        rel = module.replace(".", "/") + ".py"
        print("%s: component not found at %s" % (verb_name, tool_root / d / rel),
              file=sys.stderr)
        return 2

    if model == "required" and not _has_model(rest):
        token = _model_token(repo_root, tool_root)
        if token is not None:
            tokens = tokens + [token]

    if repo_root is None:
        kwargs = {"tool_root": tool_root, "input_fn": input_fn,
                  "output_fn": output_fn, "env": env, "cwd": cwd}
        set_config = False
    else:
        kwargs = {}
        config = Path(repo_root) / "hotdocs.toml"
        set_config = config.is_file() and _CONFIG_VAR not in os.environ
        if set_config:
            os.environ[_CONFIG_VAR] = str(config)

    try:
        with _loaded(path, base, module) as mod:
            fn = getattr(mod, "main", None)
            if fn is None:
                print("%s: not available (no main)" % verb_name, file=sys.stderr)
                return 2
            return _run(fn, tokens, kwargs)
    finally:
        if set_config:
            os.environ.pop(_CONFIG_VAR, None)


if __name__ == "__main__":
    sys.exit(main())
