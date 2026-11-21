"""The single `hotdocs` command: routes `hotdocs <verb> ...` to its component."""

import contextlib
import hashlib
import importlib
import importlib.util
import os
import sys
from pathlib import Path

TOOL_VERSION = "0.1.0"

USAGE = "usage: hotdocs <verb words> [args...] | hotdocs [--help | -h | help | --version]"

# (verb words, dir, module, strip, model, summary)
VERB_TABLE = [
    ("lint", "gen/spec-linter", "spec_linter", 1, "no", "validate the spec corpus"),
    ("impact", "gen/impact-analyzer", "impact_analyzer", 1, "no", "blast radius of a change"),
    ("assemble", "gen/spec-bundle-assembler", "spec_bundle_assembler", 1, "no", "build a component's spec bundle"),
    ("compile-criteria", "pipeline/criterion-compiler", "criterion_compiler", 1, "no", "compile the compiled criteria"),
    ("author-test", "gen/test-author", "test_author", 0, "required", "write one criterion's test"),
    ("verify-component", "gen/verifier-orchestrator", "verifier_orchestrator", 1, "no", "verify one component"),
    ("generate", "gen/component-gate-runner", "component_gate_runner", 0, "required", "generate and verify a component"),
    ("verify", "gen/provenance-tracker", "provenance_tracker", 0, "optional", "is everything ready"),
    ("track feedback", "gen/provenance-tracker", "provenance_tracker", 0, "no", "last failing requirements"),
    ("track ui build", "gen/provenance-tracker-ui", "provenance_tracker_ui", 0, "optional", "build the readiness page"),
    ("provenance check", "gen/provenance-checker", "provenance_checker", 1, "no", "is provenance a hit"),
    ("provenance write", "gen/provenance-writer", "provenance_writer", 0, "no", "write a provenance manifest"),
    ("license-scan", "gen/license-scanner", "license_scanner", 1, "no", "license scan one component"),
    ("secret-scan", "gen/secret-scanner", "secret_scanner", 1, "no", "scan for secrets"),
    ("review-packet build", "gen/review-packet-builder", "review_packet_builder", 0, "no", "build a review packet"),
    ("decision-drift", "gen/decision-drift-detector", "decision_drift_detector", 0, "no", "decisions out of step with specs"),
    ("decision-impact", "gen/decision-drift-detector", "decision_drift_detector", 0, "no", "what a decision touches"),
    ("docs-site build", "gen/docs-site-renderer", "docs_site_renderer.cli", 2, "no", "render the docs site"),
    ("corpus-graph build", "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1, "no", "build the corpus graph"),
    ("assist", "gen/spec-completeness-assistant", "spec_completeness_assistant", 1, "optional", "review a spec change"),
    ("spec check", "gen/spec-reviewer", "spec_reviewer", 2, "optional", "check criteria from their test authors' view"),
    ("decision new", "gen/spec-scaffolder", "spec_scaffolder", 0, "no", "draft the next decision record"),
    ("decision ratify", "gen/spec-scaffolder", "spec_scaffolder", 0, "no", "ratify a decision record"),
    ("decision record-commit", "gen/spec-scaffolder", "spec_scaffolder", 0, "no", "record the commit that landed a decision"),
    ("component new", "gen/spec-scaffolder", "spec_scaffolder", 0, "no", "lay out a new component"),
    ("kind new", "gen/spec-scaffolder", "spec_scaffolder", 0, "no", "scaffold a new asset kind"),
    ("init", "gen/hotdocs-init", "hotdocs_init", 1, "no", "set up a new project"),
]


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _err(message):
    print(message, file=sys.stderr)


def _default_tool_root():
    here = Path(os.path.abspath(__file__))
    for parent in here.parents:
        if parent.name == "gen":
            return str(parent.parent)
    return str(here.parent)


def _verb_lines():
    return ["  %-24s %s" % (row[0], row[5]) for row in VERB_TABLE]


def _match(argv):
    best = None
    for row in VERB_TABLE:
        words = row[0].split()
        if argv[: len(words)] == words and (best is None or len(words) > len(best[0].split())):
            best = row
    return best


def _module_file(dirpath, module):
    rel = module.replace(".", os.sep)
    for candidate in (os.path.join(dirpath, rel + ".py"), os.path.join(dirpath, rel, "__init__.py")):
        if os.path.isfile(candidate):
            return candidate
    return None


def _purge(prefix):
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            del sys.modules[name]


@contextlib.contextmanager
def _loaded(dirpath, module, repo_root):
    if "." in module:
        package = module.split(".")[0]
        _purge(package)
        sys.path.insert(0, dirpath)
        importlib.invalidate_caches()
        try:
            yield importlib.import_module(module)
        finally:
            _purge(package)
            sys.path.remove(dirpath)
        return
    path = _module_file(dirpath, module)
    digest = hashlib.sha1(os.path.abspath(repo_root).encode("utf-8")).hexdigest()[:16]
    name = "_hotdocs_cli_%s_%s" % (digest, module)
    locations = [os.path.dirname(path)] if path.endswith("__init__.py") else None
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=locations)
    mod = importlib.util.module_from_spec(spec)
    _purge(name)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
        yield mod
    finally:
        _purge(name)


def _invoke(fn, args, **keywords):
    try:
        code = fn(args, **keywords)
    except SystemExit as exc:
        code = exc.code
        if code is not None and not isinstance(code, int):
            return 1
    except Exception as exc:
        if type(exc).__name__ == "ModelResolutionError":
            _err("usage error: %s" % exc)
            return 2
        raise
    return 0 if code is None else code


def _missing(words, tool_root, dir_, module):
    path = os.path.join(tool_root, dir_, module.replace(".", os.sep) + ".py")
    _err("hotdocs: %s: component not found: %s" % (words, path))
    return 2


def _unavailable(words, module, attr):
    _err("hotdocs: %s: %s has no %s; not available" % (words, module, attr))
    return 2


def _repo_root_arg(rest, cwd):
    for i, token in enumerate(rest):
        if token.startswith("--repo-root="):
            return os.path.abspath(os.path.join(cwd, token[len("--repo-root="):]))
        if token == "--repo-root" and i + 1 < len(rest):
            return os.path.abspath(os.path.join(cwd, rest[i + 1]))
    return None


def _model_from_config(root, tool_root):
    dep_dir = os.path.join(root, "gen", "llm-endpoint")
    if not os.path.isdir(dep_dir):
        dep_dir = os.path.join(tool_root, "gen", "llm-endpoint")
    with _loaded(dep_dir, "llm_endpoint", root) as endpoint:
        config = _get(endpoint, "load_config")(Path(root) / "hotdocs.toml")
    provider = _get(config, "provider") if config is not None else None
    model = _get(config, "model") if config is not None else None
    if provider and model:
        return "%s:%s" % (provider, model)
    return None


def run(argv=None, *, tool_root=None, input_fn=None, output_fn=None, env=None, cwd=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    tool_root = _default_tool_root() if tool_root is None else tool_root
    input_fn = input if input_fn is None else input_fn
    output_fn = print if output_fn is None else output_fn
    env = os.environ if env is None else env
    cwd = os.getcwd() if cwd is None else cwd

    if not argv or argv[0] in ("help", "--help", "-h"):
        output_fn("hotdocs %s" % TOOL_VERSION)
        output_fn(USAGE)
        for line in _verb_lines():
            output_fn(line)
        return 0
    if argv[0] == "--version":
        output_fn("hotdocs %s" % TOOL_VERSION)
        return 0

    row = _match(argv)
    if row is None:
        _err("usage error: unknown verb: %s" % argv[0])
        for line in _verb_lines():
            _err(line)
        return 2

    words, dir_, module, strip, model_kind, _summary = row
    rest = argv[len(words.split()):]
    forwarded = list(argv[strip:])

    if words == "init":
        dirpath = os.path.join(tool_root, dir_)
        if _module_file(dirpath, module) is None:
            return _missing(words, tool_root, dir_, module)
        with _loaded(dirpath, module, tool_root) as mod:
            fn = getattr(mod, "run", None)
            if fn is None:
                return _unavailable(words, module, "run")
            return _invoke(fn, forwarded, tool_root=tool_root, input_fn=input_fn,
                           output_fn=output_fn, env=env, cwd=cwd)

    root = _repo_root_arg(rest, cwd)
    if root is None:
        root = os.path.abspath(cwd)
        forwarded.append("--repo-root=%s" % root)

    base = root if os.path.isdir(os.path.join(root, dir_)) else tool_root
    dirpath = os.path.join(base, dir_)
    if _module_file(dirpath, module) is None:
        return _missing(words, tool_root, dir_, module)

    if model_kind in ("required", "optional"):
        if "--no-model" in forwarded:
            forwarded = [t for t in forwarded if t != "--no-model"]
        elif not any(t == "--model" or t.startswith("--model=") for t in rest):
            try:
                model = _model_from_config(root, tool_root)
            except ValueError as exc:
                _err(str(exc))
                model = None
            if model is not None:
                forwarded.append("--model=%s" % model)
                if model_kind == "optional":
                    _err("hotdocs: using model %s from hotdocs.toml (pass --no-model to skip)" % model)

    config_path = os.path.join(root, "hotdocs.toml")
    previous = env.get("VAR_HOTDOCS_CONFIG")
    had_previous = "VAR_HOTDOCS_CONFIG" in env
    set_config = os.path.isfile(config_path) and not previous
    if set_config:
        env["VAR_HOTDOCS_CONFIG"] = config_path
    try:
        with _loaded(dirpath, module, root) as mod:
            fn = getattr(mod, "main", None)
            if fn is None:
                return _unavailable(words, module, "main")
            return _invoke(fn, forwarded)
    finally:
        if set_config:
            if had_previous:
                env["VAR_HOTDOCS_CONFIG"] = previous
            else:
                del env["VAR_HOTDOCS_CONFIG"]


def main(argv=None):
    return run(argv)
