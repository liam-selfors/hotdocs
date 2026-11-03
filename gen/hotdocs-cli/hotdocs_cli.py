import importlib
import importlib.util
import os
import sys
import uuid

TOOL_VERSION = "0.1.0"

VERB_TABLE = (
    {"words": ("lint",), "dir": "gen/spec-linter", "module": "spec_linter",
     "strip": 1, "model": "no", "summary": "validate the spec corpus"},
    {"words": ("impact",), "dir": "gen/impact-analyzer", "module": "impact_analyzer",
     "strip": 1, "model": "no", "summary": "blast radius of a change"},
    {"words": ("assemble",), "dir": "gen/spec-bundle-assembler", "module": "spec_bundle_assembler",
     "strip": 1, "model": "no", "summary": "build a component's spec bundle"},
    {"words": ("compile-criteria",), "dir": "pipeline/criterion-compiler", "module": "criterion_compiler",
     "strip": 1, "model": "no", "summary": "compile the compiled criteria"},
    {"words": ("author-test",), "dir": "gen/test-author", "module": "test_author",
     "strip": 0, "model": "required", "summary": "write one criterion's test"},
    {"words": ("verify-component",), "dir": "gen/verifier-orchestrator", "module": "verifier_orchestrator",
     "strip": 1, "model": "no", "summary": "verify one component"},
    {"words": ("generate",), "dir": "gen/component-gate-runner", "module": "component_gate_runner",
     "strip": 0, "model": "required", "summary": "generate and verify a component"},
    {"words": ("verify",), "dir": "gen/provenance-tracker", "module": "provenance_tracker",
     "strip": 0, "model": "no", "summary": "is everything ready"},
    {"words": ("track", "feedback"), "dir": "gen/provenance-tracker", "module": "provenance_tracker",
     "strip": 0, "model": "no", "summary": "last failing requirements"},
    {"words": ("track", "ui", "build"), "dir": "gen/provenance-tracker-ui", "module": "provenance_tracker_ui",
     "strip": 0, "model": "no", "summary": "build the readiness page"},
    {"words": ("provenance", "check"), "dir": "gen/provenance-checker", "module": "provenance_checker",
     "strip": 1, "model": "no", "summary": "is provenance a hit"},
    {"words": ("provenance", "write"), "dir": "gen/provenance-writer", "module": "provenance_writer",
     "strip": 0, "model": "no", "summary": "write a provenance manifest"},
    {"words": ("license-scan",), "dir": "gen/license-scanner", "module": "license_scanner",
     "strip": 1, "model": "no", "summary": "license scan one component"},
    {"words": ("secret-scan",), "dir": "gen/secret-scanner", "module": "secret_scanner",
     "strip": 1, "model": "no", "summary": "scan for secrets"},
    {"words": ("review-packet", "build"), "dir": "gen/review-packet-builder", "module": "review_packet_builder",
     "strip": 0, "model": "no", "summary": "build a review packet"},
    {"words": ("decision-drift",), "dir": "gen/decision-drift-detector", "module": "decision_drift_detector",
     "strip": 0, "model": "no", "summary": "decisions out of step with specs"},
    {"words": ("decision-impact",), "dir": "gen/decision-drift-detector", "module": "decision_drift_detector",
     "strip": 0, "model": "no", "summary": "what a decision touches"},
    {"words": ("docs-site", "build"), "dir": "gen/docs-site-renderer", "module": "docs_site_renderer.cli",
     "strip": 2, "model": "no", "summary": "render the docs site"},
    {"words": ("corpus-graph", "build"), "dir": "gen/corpus-graph-builder", "module": "corpus_graph_builder.cli",
     "strip": 1, "model": "no", "summary": "build the corpus graph"},
    {"words": ("assist",), "dir": "gen/spec-completeness-assistant", "module": "spec_completeness_assistant",
     "strip": 1, "model": "no", "summary": "review a spec change"},
    {"words": ("init",), "dir": "gen/hotdocs-init", "module": "hotdocs_init",
     "strip": 1, "model": "no", "summary": "set up a new project", "is_init": True},
)


def _dget(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _find_row(argv):
    best = None
    for row in VERB_TABLE:
        words = row["words"]
        n = len(words)
        if len(argv) >= n and tuple(argv[:n]) == words:
            if best is None or n > len(best["words"]):
                best = row
    return best


def _verb_list_lines():
    lines = ["Verbs:"]
    for row in VERB_TABLE:
        verb_str = " ".join(row["words"])
        lines.append("  {:<24} {}".format(verb_str, row["summary"]))
    return lines


def _print_help(output_fn):
    output_fn("hotdocs {}".format(TOOL_VERSION))
    output_fn("Usage: hotdocs <verb> [args...]")
    for line in _verb_list_lines():
        output_fn(line)


def _print_unknown(word):
    print("unknown verb: {}".format(word), file=sys.stderr)
    for line in _verb_list_lines():
        print(line, file=sys.stderr)


def _purge_package(package_name):
    for name in list(sys.modules):
        if name == package_name or name.startswith(package_name + "."):
            del sys.modules[name]


def _load_flat_module(repo_root, dir_, module_name):
    file_path = os.path.join(os.path.abspath(repo_root), dir_, module_name + ".py")
    if not os.path.isfile(file_path):
        return None, file_path
    unique_name = "_hotdocs_dyn_{}".format(uuid.uuid4().hex)
    spec = importlib.util.spec_from_file_location(unique_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(unique_name, None)
    return mod, file_path


def _load_dotted_module(repo_root, dir_, module_name):
    base_dir = os.path.join(os.path.abspath(repo_root), dir_)
    package_name = module_name.split(".")[0]
    file_path = os.path.join(base_dir, *module_name.split(".")) + ".py"
    if not os.path.isfile(file_path):
        return None, file_path
    _purge_package(package_name)
    sys.path.insert(0, base_dir)
    try:
        mod = importlib.import_module(module_name)
    finally:
        try:
            sys.path.remove(base_dir)
        except ValueError:
            pass
        _purge_package(package_name)
    return mod, file_path


def _load_module(repo_root, dir_, module_name):
    if "." in module_name:
        return _load_dotted_module(repo_root, dir_, module_name)
    return _load_flat_module(repo_root, dir_, module_name)


def _normalize_exit(code):
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _has_flag(tokens, name):
    for t in tokens:
        if t == name or t.startswith(name + "="):
            return True
    return False


def _find_repo_root_value(tokens):
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "--repo-root":
            return tokens[i + 1] if i + 1 < len(tokens) else None
        if t.startswith("--repo-root="):
            return t[len("--repo-root="):]
        i += 1
    return None


def _resolve_model(repo_root):
    mod, _ = _load_flat_module(repo_root, "gen/llm-endpoint", "llm_endpoint")
    if mod is None:
        return None
    load_config = getattr(mod, "load_config", None)
    if load_config is None:
        return None
    config_path = os.path.join(os.path.abspath(repo_root), "hotdocs.toml")
    try:
        config = load_config(config_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return None
    if config is None:
        return None
    provider = _dget(config, "provider")
    model = _dget(config, "model")
    if not provider or not model:
        return None
    return "{}:{}".format(provider, model)


def _dispatch_init(row, argv, tool_root, input_fn, output_fn, env, cwd):
    forwarded = list(argv[row["strip"]:])
    base_dir = tool_root if tool_root else cwd
    mod, _ = _load_module(base_dir, row["dir"], row["module"])
    if mod is None:
        display = "{}/{}.py".format(row["dir"], row["module"])
        print(
            "component not found: {} (run `hotdocs init`)".format(display),
            file=sys.stderr,
        )
        return 2
    main_fn = getattr(mod, "main", None)
    if main_fn is None:
        print(
            "{} has no main: not available".format(row["module"]),
            file=sys.stderr,
        )
        return 2
    try:
        result = main_fn(
            forwarded,
            tool_root=tool_root,
            input_fn=input_fn,
            output_fn=output_fn,
            env=env,
            cwd=cwd,
        )
    except SystemExit as exc:
        result = exc.code
    return _normalize_exit(result)


def _dispatch_verb(row, argv, env, cwd):
    words = row["words"]
    forwarded = list(argv[row["strip"]:])
    rest_after_words = argv[len(words):]

    repo_root_value = _find_repo_root_value(rest_after_words)
    if repo_root_value is not None:
        repo_root = os.path.abspath(repo_root_value)
    else:
        repo_root = os.path.abspath(cwd)
        forwarded = forwarded + ["--repo-root={}".format(repo_root)]

    if row["model"] == "required" and not _has_flag(rest_after_words, "--model"):
        model_str = _resolve_model(repo_root)
        if model_str is not None:
            forwarded = forwarded + ["--model={}".format(model_str)]

    mod, _ = _load_module(repo_root, row["dir"], row["module"])
    if mod is None:
        display = "{}/{}.py".format(row["dir"], row["module"])
        print(
            "component not found: {} (run `hotdocs init`)".format(display),
            file=sys.stderr,
        )
        return 2
    main_fn = getattr(mod, "main", None)
    if main_fn is None:
        print(
            "{} has no main: not available".format(row["module"]),
            file=sys.stderr,
        )
        return 2

    config_path = os.path.join(repo_root, "hotdocs.toml")
    had_key = "VAR_HOTDOCS_CONFIG" in env
    old_value = env.get("VAR_HOTDOCS_CONFIG") if had_key else None
    set_now = False
    if not env.get("VAR_HOTDOCS_CONFIG") and os.path.exists(config_path):
        env["VAR_HOTDOCS_CONFIG"] = config_path
        set_now = True
    try:
        try:
            result = main_fn(forwarded)
        except SystemExit as exc:
            result = exc.code
    finally:
        if set_now:
            if had_key:
                env["VAR_HOTDOCS_CONFIG"] = old_value
            else:
                env.pop("VAR_HOTDOCS_CONFIG", None)

    return _normalize_exit(result)


def main(argv=None, *, tool_root=None, input_fn=None, output_fn=None,
         env=None, cwd=None):
    if argv is None:
        argv = sys.argv[1:]
    if input_fn is None:
        input_fn = input
    if output_fn is None:
        output_fn = print
    if env is None:
        env = os.environ
    if cwd is None:
        cwd = os.getcwd()

    if not argv or argv[0] in ("help", "--help", "-h"):
        _print_help(output_fn)
        return 0

    if argv[0] == "--version":
        output_fn("hotdocs {}".format(TOOL_VERSION))
        return 0

    row = _find_row(argv)
    if row is None:
        _print_unknown(argv[0])
        return 2

    if row.get("is_init"):
        return _dispatch_init(row, argv, tool_root, input_fn, output_fn, env, cwd)

    return _dispatch_verb(row, argv, env, cwd)