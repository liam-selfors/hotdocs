"""The `hotdocs` dispatcher: routes `hotdocs <verb> ...` to its component."""

import importlib
import importlib.util
import os
import sys
import uuid
from collections import namedtuple
from pathlib import Path

TOOL_VERSION = "0.1.0"

VerbRow = namedtuple("VerbRow", ["words", "dir", "module", "strip", "model", "summary"])

VERB_TABLE = [
    VerbRow(("lint",), "gen/spec-linter", "spec_linter", 1, "no",
            "validate the spec corpus"),
    VerbRow(("impact",), "gen/impact-analyzer", "impact_analyzer", 1, "no",
            "blast radius of a change"),
    VerbRow(("assemble",), "gen/spec-bundle-assembler", "spec_bundle_assembler", 1, "no",
            "build a component's spec bundle"),
    VerbRow(("compile-criteria",), "pipeline/criterion-compiler", "criterion_compiler", 1, "no",
            "compile the compiled criteria"),
    VerbRow(("author-test",), "gen/test-author", "test_author", 0, "required",
            "write one criterion's test"),
    VerbRow(("verify-component",), "gen/verifier-orchestrator", "verifier_orchestrator", 1, "no",
            "verify one component"),
    VerbRow(("generate",), "gen/component-gate-runner", "component_gate_runner", 0, "required",
            "generate and verify a component"),
    VerbRow(("verify",), "gen/provenance-tracker", "provenance_tracker", 0, "no",
            "is everything ready"),
    VerbRow(("track", "feedback"), "gen/provenance-tracker", "provenance_tracker", 0, "no",
            "last failing requirements"),
    VerbRow(("track", "ui", "build"), "gen/provenance-tracker-ui", "provenance_tracker_ui", 0, "no",
            "build the readiness page"),
    VerbRow(("provenance", "check"), "gen/provenance-checker", "provenance_checker", 1, "no",
            "is provenance a hit"),
    VerbRow(("provenance", "write"), "gen/provenance-writer", "provenance_writer", 0, "no",
            "write a provenance manifest"),
    VerbRow(("license-scan",), "gen/license-scanner", "license_scanner", 1, "no",
            "license scan one component"),
    VerbRow(("secret-scan",), "gen/secret-scanner", "secret_scanner", 1, "no",
            "scan for secrets"),
    VerbRow(("review-packet", "build"), "gen/review-packet-builder", "review_packet_builder", 0, "no",
            "build a review packet"),
    VerbRow(("decision-drift",), "gen/decision-drift-detector", "decision_drift_detector", 0, "no",
            "decisions out of step with specs"),
    VerbRow(("decision-impact",), "gen/decision-drift-detector", "decision_drift_detector", 0, "no",
            "what a decision touches"),
    VerbRow(("docs-site", "build"), "gen/docs-site-renderer", "docs_site_renderer.cli", 2, "no",
            "render the docs site"),
    VerbRow(("corpus-graph", "build"), "gen/corpus-graph-builder", "corpus_graph_builder.cli", 1, "no",
            "build the corpus graph"),
    VerbRow(("assist",), "gen/spec-completeness-assistant", "spec_completeness_assistant", 1, "no",
            "review a spec change"),
    VerbRow(("init",), "gen/hotdocs-init", "hotdocs_init", 1, "no",
            "set up a new project"),
]


def _default_tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise RuntimeError("hotdocs: could not locate tool root (no 'gen' ancestor)")


def _resolve_tool_root(tool_root):
    if tool_root is not None:
        return str(tool_root)
    return str(_default_tool_root())


def _find_row(argv):
    best = None
    for row in VERB_TABLE:
        n = len(row.words)
        if n > len(argv):
            continue
        if tuple(argv[:n]) == row.words:
            if best is None or n > len(best.words):
                best = row
    return best


def _module_rel_path(module_name):
    return module_name.replace(".", os.sep) + ".py"


def _clear_package_modules(top_name):
    for name in list(sys.modules):
        if name == top_name or name.startswith(top_name + "."):
            del sys.modules[name]


def _load_from_dir(base_dir, module_name):
    rel = _module_rel_path(module_name)
    file_path = os.path.join(base_dir, rel)
    if not os.path.isfile(file_path):
        raise FileNotFoundError(file_path)

    if "." in module_name:
        top = module_name.split(".", 1)[0]
        _clear_package_modules(top)
        sys.path.insert(0, base_dir)
        try:
            mod = importlib.import_module(module_name)
        finally:
            try:
                sys.path.remove(base_dir)
            except ValueError:
                pass

        def cleanup():
            _clear_package_modules(top)

        return mod, cleanup

    unique_name = "_hotdocs_cli_dyn_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(unique_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)

    def cleanup():
        sys.modules.pop(unique_name, None)

    return mod, cleanup


def _resolve_base_dir(dir_, module_name, repo_root, tool_root):
    repo_dir = os.path.join(repo_root, dir_)
    tool_dir = os.path.join(tool_root, dir_)
    rel = _module_rel_path(module_name)

    base_dir = repo_dir if os.path.isdir(repo_dir) else tool_dir
    if os.path.isfile(os.path.join(base_dir, rel)):
        return base_dir

    other_dir = tool_dir if base_dir == repo_dir else repo_dir
    if os.path.isfile(os.path.join(other_dir, rel)):
        return other_dir

    return None


def _extract_repo_root(args):
    for i, tok in enumerate(args):
        if tok == "--repo-root" and i + 1 < len(args):
            return args[i + 1]
        if tok.startswith("--repo-root="):
            return tok[len("--repo-root="):]
    return None


def _has_model_flag(args):
    for tok in args:
        if tok == "--model" or tok.startswith("--model="):
            return True
    return False


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _call_load_config(repo_root, tool_root):
    base_dir = _resolve_base_dir("gen/llm-endpoint", "llm_endpoint", repo_root, tool_root)
    if base_dir is None:
        return None
    mod, cleanup = _load_from_dir(base_dir, "llm_endpoint")
    try:
        config_path = Path(repo_root) / "hotdocs.toml"
        return mod.load_config(config_path)
    finally:
        cleanup()


def _code_from_system_exit(exc):
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, int):
        return code
    return 1


def _result_code(result):
    if result is None:
        return 0
    return result


def _usage_line():
    return "usage: hotdocs <verb> [args...]"


def _verb_list_lines():
    lines = []
    for row in VERB_TABLE:
        words = " ".join(row.words)
        lines.append("  {:<24} {}".format(words, row.summary))
    return lines


def _print_help(output_fn):
    output_fn("hotdocs {}".format(TOOL_VERSION))
    output_fn(_usage_line())
    for line in _verb_list_lines():
        output_fn(line)


def _print_error_with_verb_list(message):
    print(message, file=sys.stderr)
    for line in _verb_list_lines():
        print(line, file=sys.stderr)


def _dispatch_init(row, argv, tool_root, input_fn, output_fn, env, cwd):
    forwarded = list(argv[row.strip:])
    base_dir = os.path.join(tool_root, row.dir)
    rel = _module_rel_path(row.module)
    file_path = os.path.join(base_dir, rel)
    if not os.path.isfile(file_path):
        print("hotdocs: component not found: {}".format(file_path), file=sys.stderr)
        return 2

    mod, cleanup = _load_from_dir(base_dir, row.module)
    try:
        main_fn = mod.main if hasattr(mod, "main") else None
        if main_fn is None:
            print(
                "hotdocs: '{}' is not available (no main in {})".format(
                    " ".join(row.words), row.module
                ),
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
            return _code_from_system_exit(exc)
        return _result_code(result)
    finally:
        cleanup()


def _dispatch_verb(row, argv, tool_root, env, cwd):
    n = len(row.words)
    rest = argv[n:]
    forwarded = list(argv[row.strip:])

    repo_root_arg = _extract_repo_root(rest)
    if repo_root_arg is None:
        repo_root = os.path.abspath(cwd)
        forwarded = forwarded + ["--repo-root={}".format(repo_root)]
    else:
        repo_root = os.path.abspath(repo_root_arg)

    if row.model == "required" and not _has_model_flag(rest):
        try:
            config = _call_load_config(repo_root, tool_root)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
        else:
            if config is not None:
                provider = _get(config, "provider")
                model = _get(config, "model")
                if provider and model:
                    forwarded = forwarded + ["--model={}:{}".format(provider, model)]

    base_dir = _resolve_base_dir(row.dir, row.module, repo_root, tool_root)
    if base_dir is None:
        tool_file = os.path.join(tool_root, row.dir, _module_rel_path(row.module))
        print("hotdocs: component not found: {}".format(tool_file), file=sys.stderr)
        return 2

    mod, cleanup = _load_from_dir(base_dir, row.module)
    try:
        main_fn = mod.main if hasattr(mod, "main") else None
        if main_fn is None:
            print(
                "hotdocs: '{}' is not available (no main in {})".format(
                    " ".join(row.words), row.module
                ),
                file=sys.stderr,
            )
            return 2

        config_file = os.path.join(repo_root, "hotdocs.toml")
        had_var = bool(env.get("VAR_HOTDOCS_CONFIG"))
        set_var = False
        if os.path.isfile(config_file) and not had_var:
            env["VAR_HOTDOCS_CONFIG"] = config_file
            set_var = True
        try:
            try:
                result = main_fn(forwarded)
            except SystemExit as exc:
                return _code_from_system_exit(exc)
            return _result_code(result)
        finally:
            if set_var:
                env.pop("VAR_HOTDOCS_CONFIG", None)
    finally:
        cleanup()


def main(argv=None, *, tool_root=None, input_fn=None, output_fn=None, env=None, cwd=None):
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

    resolved_tool_root = _resolve_tool_root(tool_root)

    if not argv or argv[0] in ("help", "--help", "-h"):
        _print_help(output_fn)
        return 0
    if argv[0] == "--version":
        output_fn("hotdocs {}".format(TOOL_VERSION))
        return 0

    row = _find_row(argv)
    if row is None:
        _print_error_with_verb_list("unknown verb: {}".format(argv[0]))
        return 2

    if row.words == ("init",):
        return _dispatch_init(row, argv, resolved_tool_root, input_fn, output_fn, env, cwd)

    return _dispatch_verb(row, argv, resolved_tool_root, env, cwd)