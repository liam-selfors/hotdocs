"""The single ``hotdocs`` command: routes ``hotdocs <verb> ...`` to a component."""

import contextlib
import hashlib
import importlib
import importlib.util
import io
import os
import sys
import tomllib
from pathlib import Path

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
    (("capability", "new"), "gen/spec-scaffolder", "spec_scaffolder", 0, "no",
     "lay out a new capability"),
    (("init",), "gen/hotdocs-init", "hotdocs_init", 1, "no", "set up a new project"),
]

USAGE = "usage: hotdocs <verb words> [args...] | hotdocs [--help | -h | help | --version]"

LLM_DIR = "gen/llm-endpoint"
LLM_MODULE = "llm_endpoint"
CONFIG_VAR = "VAR_HOTDOCS_CONFIG"


def _default_tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return str(parent.parent)
    return str(here.parent)


def _tool_version(tool_root):
    try:
        with open(os.path.join(tool_root, "pyproject.toml"), "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, ValueError):
        return "unknown"
    project = data.get("project")
    if not isinstance(project, dict):
        return "unknown"
    version = project.get("version")
    if isinstance(version, str) and version:
        return version
    return "unknown"


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _verb_lines():
    width = max(len(" ".join(row[0])) for row in VERB_TABLE)
    return ["  %-*s  %s" % (width, " ".join(row[0]), row[5]) for row in VERB_TABLE]


def _match(argv):
    best = None
    for row in VERB_TABLE:
        words = list(row[0])
        if argv[:len(words)] == words and (best is None or len(words) > len(best[0])):
            best = row
    return best


def _repo_root_arg(args):
    for i, tok in enumerate(args):
        if tok.startswith("--repo-root="):
            return tok[len("--repo-root="):]
        if tok == "--repo-root" and i + 1 < len(args):
            return args[i + 1]
    return None


def _choose_base(repo_root, tool_root, dir_):
    if os.path.isdir(os.path.join(repo_root, dir_)):
        return repo_root
    return tool_root


def _rel(module):
    return module.replace(".", os.sep)


def _locate(base, dir_, module):
    rel = _rel(module)
    file_path = os.path.join(base, dir_, rel + ".py")
    if os.path.isfile(file_path):
        return file_path, False
    pkg_path = os.path.join(base, dir_, rel, "__init__.py")
    if os.path.isfile(pkg_path):
        return pkg_path, True
    return None


def _purge(prefix):
    for key in list(sys.modules):
        if key == prefix or key.startswith(prefix + "."):
            del sys.modules[key]


@contextlib.contextmanager
def _loaded(base, dir_, module, found, root_key):
    path, is_pkg = found
    if "." in module:
        pkg = module.split(".")[0]
        search_dir = os.path.join(base, dir_)
        _purge(pkg)
        sys.path.insert(0, search_dir)
        try:
            importlib.invalidate_caches()
            yield importlib.import_module(module)
        finally:
            if search_dir in sys.path:
                sys.path.remove(search_dir)
            _purge(pkg)
        return
    digest = hashlib.sha256(str(root_key).encode("utf-8")).hexdigest()[:16]
    name = "_hotdocs_cli_%s_%s" % (digest, module)
    _purge(name)
    if is_pkg:
        spec = importlib.util.spec_from_file_location(
            name, path, submodule_search_locations=[os.path.dirname(path)])
    else:
        spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
        yield mod
    finally:
        _purge(name)


@contextlib.contextmanager
def _config_env(repo_root):
    path = os.path.join(repo_root, "hotdocs.toml")
    prior = os.environ.get(CONFIG_VAR)
    if prior or not os.path.isfile(path):
        yield
        return
    os.environ[CONFIG_VAR] = path
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(CONFIG_VAR, None)
        else:
            os.environ[CONFIG_VAR] = prior


def _apply_model(model, forwarded, repo_root, tool_root):
    if "--no-model" in forwarded:
        return [t for t in forwarded if t != "--no-model"]
    if any(t == "--model" or t.startswith("--model=") for t in forwarded):
        return forwarded
    base = _choose_base(repo_root, tool_root, LLM_DIR)
    found = _locate(base, LLM_DIR, LLM_MODULE)
    if found is None:
        return forwarded
    with _loaded(base, LLM_DIR, LLM_MODULE, found, repo_root) as llm:
        try:
            cfg = llm.load_config(Path(os.path.join(repo_root, "hotdocs.toml")))
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return forwarded
    if cfg is None:
        return forwarded
    provider = _get(cfg, "provider")
    model_name = _get(cfg, "model")
    if not provider or not model_name:
        return forwarded
    model_string = "%s:%s" % (provider, model_name)
    if model == "optional":
        print("hotdocs: using model %s from hotdocs.toml (pass --no-model to skip)"
              % model_string, file=sys.stderr)
    return forwarded + ["--model=" + model_string]


def _invoke(fn, args, kwargs):
    try:
        rc = fn(args, **kwargs)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    except Exception as exc:
        if type(exc).__name__ == "ModelResolutionError":
            print("usage error: " + " ".join(str(exc).splitlines()), file=sys.stderr)
            return 2
        raise
    return 0 if rc is None else rc


def run(argv=None, *, tool_root=None, input_fn=None, output_fn=None, env=None, cwd=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    tool_root = _default_tool_root() if tool_root is None else os.fspath(tool_root)
    input_fn = input if input_fn is None else input_fn
    output_fn = print if output_fn is None else output_fn
    env = os.environ if env is None else env
    cwd = os.getcwd() if cwd is None else os.fspath(cwd)

    if not argv or argv[0] in ("help", "--help", "-h"):
        output_fn("hotdocs " + _tool_version(tool_root))
        output_fn(USAGE)
        for line in _verb_lines():
            output_fn(line)
        return 0
    if argv[0] == "--version":
        output_fn("hotdocs " + _tool_version(tool_root))
        return 0

    row = _match(argv)
    if row is None:
        print("usage error: unknown verb: " + argv[0], file=sys.stderr)
        for line in _verb_lines():
            print(line, file=sys.stderr)
        return 2

    words, dir_, module, strip, model, summary = row
    verb = " ".join(words)
    args = argv[len(words):]
    forwarded = list(argv[strip:])
    help_mode = "--help" in args or "-h" in args
    is_init = words == ("init",)

    if is_init:
        repo_root = None
        base = tool_root
        root_key = tool_root
    else:
        given = _repo_root_arg(args)
        if given is None:
            repo_root = os.path.abspath(cwd)
            forwarded.append("--repo-root=" + repo_root)
        else:
            repo_root = os.path.abspath(os.path.join(cwd, given))
        base = _choose_base(repo_root, tool_root, dir_)
        root_key = repo_root

    found = _locate(base, dir_, module)
    if found is None:
        print("hotdocs: %s: component not found: %s"
              % (verb, os.path.join(tool_root, dir_, _rel(module) + ".py")), file=sys.stderr)
        return 2

    buf = None
    saved_err = sys.stderr
    if help_mode:
        buf = io.StringIO()
        sys.stderr = buf
    try:
        env_ctx = contextlib.nullcontext() if is_init else _config_env(repo_root)
        with env_ctx, _loaded(base, dir_, module, found, root_key) as mod:
            attr = "run" if is_init else "main"
            fn = getattr(mod, attr, None)
            if fn is None:
                print("hotdocs: %s: not available (%s has no %s)" % (verb, found[0], attr),
                      file=sys.stderr)
                code = 2
            else:
                if not help_mode and model in ("required", "optional"):
                    forwarded = _apply_model(model, forwarded, repo_root, tool_root)
                if is_init:
                    kwargs = {"tool_root": tool_root, "input_fn": input_fn,
                              "output_fn": output_fn, "env": env, "cwd": cwd}
                else:
                    kwargs = {}
                code = _invoke(fn, forwarded, kwargs)
    finally:
        sys.stderr = saved_err

    if not help_mode:
        return code
    text = buf.getvalue()
    lines = text.splitlines()
    if code == 2 and lines and lines[0].startswith("usage error:"):
        output_fn("hotdocs %s: %s" % (verb, summary))
        for line in lines[1:]:
            if line.strip():
                output_fn(line)
        return 0
    sys.stderr.write(text)
    return code


def main(argv=None):
    return run(argv)
