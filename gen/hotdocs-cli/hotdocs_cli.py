"""The single `hotdocs` command: routes `hotdocs <verb> ...` to its component."""

import contextlib
import hashlib
import importlib
import importlib.util
import os
import sys
from collections.abc import Mapping
from pathlib import Path

TOOL_VERSION = "0.1.0"

USAGE = "usage: hotdocs <verb words> [args...]"

HELP_WORDS = ("help", "--help", "-h")

CONFIG_VAR = "VAR_HOTDOCS_CONFIG"

LLM_ENDPOINT_DIR = "gen/llm-endpoint"
LLM_ENDPOINT_MODULE = "llm_endpoint"

# (verb words, dir, module, strip, model, summary)
VERB_TABLE = (
    ("lint", "gen/spec-linter", "spec_linter", 1, "no", "validate the spec corpus"),
    ("impact", "gen/impact-analyzer", "impact_analyzer", 1, "no", "blast radius of a change"),
    ("assemble", "gen/spec-bundle-assembler", "spec_bundle_assembler", 1, "no",
     "build a component's spec bundle"),
    ("compile-criteria", "pipeline/criterion-compiler", "criterion_compiler", 1, "no",
     "compile the compiled criteria"),
    ("author-test", "gen/test-author", "test_author", 0, "required",
     "write one criterion's test"),
    ("verify-component", "gen/verifier-orchestrator", "verifier_orchestrator", 1, "no",
     "verify one component"),
    ("generate", "gen/component-gate-runner", "component_gate_runner", 0, "required",
     "generate and verify a component"),
    ("verify", "gen/provenance-tracker", "provenance_tracker", 0, "no", "is everything ready"),
    ("track feedback", "gen/provenance-tracker", "provenance_tracker", 0, "no",
     "last failing requirements"),
    ("track ui build", "gen/provenance-tracker-ui", "provenance_tracker_ui", 0, "no",
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
    ("assist", "gen/spec-completeness-assistant", "spec_completeness_assistant", 1, "no",
     "review a spec change"),
    ("init", "gen/hotdocs-init", "hotdocs_init", 1, "no", "set up a new project"),
)


def _default_tool_root():
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _field(obj, key):
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _verb_lines():
    return [f"  {row[0]:<20} {row[5]}" for row in VERB_TABLE]


def _match(argv):
    for row in sorted(VERB_TABLE, key=lambda r: -len(r[0].split())):
        words = row[0].split()
        if argv[:len(words)] == words:
            return row
    return None


def _repo_root_arg(args):
    for i, token in enumerate(args):
        if token.startswith("--repo-root="):
            return token[len("--repo-root="):]
        if token == "--repo-root":
            return args[i + 1]
    return None


def _module_file(base, directory, module):
    rel = module.replace(".", "/")
    flat = Path(base) / directory / (rel + ".py")
    if flat.is_file():
        return flat
    package = Path(base) / directory / rel / "__init__.py"
    if package.is_file():
        return package
    return None


def _purge(name):
    for key in [k for k in sys.modules if k == name or k.startswith(name + ".")]:
        del sys.modules[key]


def _base_for(repo, directory, tool_path):
    return repo if (repo / directory).exists() else tool_path


@contextlib.contextmanager
def _loaded(base, directory, module):
    if "." in module:
        path = str(Path(base) / directory)
        package = module.split(".")[0]
        _purge(package)
        sys.path.insert(0, path)
        importlib.invalidate_caches()
        try:
            yield importlib.import_module(module)
        finally:
            _purge(package)
            sys.path.remove(path)
    else:
        digest = hashlib.sha256(str(base).encode("utf-8")).hexdigest()[:16]
        name = f"_hotdocs_cli_{module}_{digest}"
        spec = importlib.util.spec_from_file_location(name, _module_file(base, directory, module))
        mod = importlib.util.module_from_spec(spec)
        try:
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            yield mod
        finally:
            _purge(name)


def _exit_code(code):
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _inject_model(repo, tool_path, forwarded):
    base = _base_for(repo, LLM_ENDPOINT_DIR, tool_path)
    with _loaded(base, LLM_ENDPOINT_DIR, LLM_ENDPOINT_MODULE) as endpoint:
        try:
            config = endpoint.load_config(repo / "hotdocs.toml")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return
    provider = _field(config, "provider")
    model = _field(config, "model")
    if provider and model:
        forwarded.append(f"--model={provider}:{model}")


def main(argv=None, *, tool_root=None, input_fn=None, output_fn=None, env=None, cwd=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    input_fn = input if input_fn is None else input_fn
    output_fn = print if output_fn is None else output_fn
    env = os.environ if env is None else env
    cwd = os.getcwd() if cwd is None else cwd
    tool_root = _default_tool_root() if tool_root is None else tool_root
    tool_path = Path(tool_root)

    if not argv or argv[0] in HELP_WORDS:
        output_fn(f"hotdocs {TOOL_VERSION}")
        output_fn(USAGE)
        for line in _verb_lines():
            output_fn(line)
        return 0
    if argv[0] == "--version":
        output_fn(f"hotdocs {TOOL_VERSION}")
        return 0

    row = _match(argv)
    if row is None:
        print(f"unknown verb: {argv[0]}", file=sys.stderr)
        for line in _verb_lines():
            print(line, file=sys.stderr)
        return 2

    verb, directory, module, strip, model_mode, _summary = row
    words = verb.split()
    args = argv[len(words):]
    forwarded = list(argv[strip:])
    kwargs = {}
    set_config = False
    config_file = None

    if verb == "init":
        base = tool_path
        kwargs = {
            "tool_root": tool_root,
            "input_fn": input_fn,
            "output_fn": output_fn,
            "env": env,
            "cwd": cwd,
        }
    else:
        value = _repo_root_arg(args)
        repo = Path(os.path.abspath(Path(cwd) if value is None else Path(cwd, value)))
        if value is None:
            forwarded.append(f"--repo-root={repo}")
        base = _base_for(repo, directory, tool_path)
        config_file = repo / "hotdocs.toml"
        set_config = config_file.exists() and not env.get(CONFIG_VAR)

    if _module_file(base, directory, module) is None:
        missing = tool_path / directory / (module.replace(".", "/") + ".py")
        print(f"hotdocs: {verb}: component not found: {missing}", file=sys.stderr)
        return 2

    if model_mode == "required" and not any(
        t == "--model" or t.startswith("--model=") for t in args
    ):
        _inject_model(repo, tool_path, forwarded)

    previous = env.get(CONFIG_VAR)
    if set_config:
        env[CONFIG_VAR] = str(config_file)
    try:
        with _loaded(base, directory, module) as mod:
            component_main = getattr(mod, "main", None)
            if component_main is None:
                print(f"hotdocs: {verb}: not available (no main)", file=sys.stderr)
                return 2
            result = component_main(forwarded, **kwargs)
    except SystemExit as exc:
        return _exit_code(exc.code)
    finally:
        if set_config:
            if previous is None:
                env.pop(CONFIG_VAR, None)
            else:
                env[CONFIG_VAR] = previous
    return 0 if result is None else result
