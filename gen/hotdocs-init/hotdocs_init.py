"""Project initialization for the hotdocs tool (comp-hotdocs-init)."""

import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

TOOL_VERSION = "0.1.0"

_SKELETON_DIRS = ["specs/product", "specs/components", "specs/decisions", "gen", "verification"]
_GITKEEP_DIRS = ["specs/product", "specs/components", "specs/decisions", "verification"]
_GITIGNORE_LINES = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]

_FLAG_SPECS = {
    "--example": "bool",
    "--reconfigure": "bool",
    "--no-test": "bool",
    "--yes": "bool",
    "--provider": "value",
    "--model": "value",
    "--base-url": "value",
    "--api-key-env": "value",
}

_API_KEY_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class UsageError(Exception):
    pass


class _Options:
    def __init__(self):
        self.dir = None
        self.example = False
        self.reconfigure = False
        self.no_test = False
        self.yes = False
        self.provider = None
        self.model = None
        self.base_url = None
        self.api_key_env = None


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _attr_name(flag):
    return flag.lstrip("-").replace("-", "_")


def _parse_args(argv):
    opts = _Options()
    i = 0
    n = len(argv)
    positional_seen = False
    while i < n:
        arg = argv[i]
        if arg.startswith("--"):
            if "=" in arg:
                flag, _, value = arg.partition("=")
            else:
                flag, value = arg, None
            if flag not in _FLAG_SPECS:
                raise UsageError(f"unknown flag: {flag}")
            kind = _FLAG_SPECS[flag]
            if kind == "bool":
                if value is not None:
                    raise UsageError(f"unknown flag: {arg}")
                setattr(opts, _attr_name(flag), True)
                i += 1
            else:
                if value is None:
                    if i + 1 >= n:
                        raise UsageError(f"{flag} requires a value")
                    value = argv[i + 1]
                    i += 2
                else:
                    i += 1
                setattr(opts, _attr_name(flag), value)
        else:
            if positional_seen:
                raise UsageError(f"unexpected extra argument: {arg}")
            opts.dir = arg
            positional_seen = True
            i += 1
    return opts


def _load_llm_endpoint(tool_root):
    path = Path(tool_root) / "gen" / "llm-endpoint" / "llm_endpoint.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("llm_endpoint", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_endpoint"] = module
    spec.loader.exec_module(module)
    return module


def _check_refusal(target_dir, tool_root):
    target_resolved = Path(target_dir).resolve()
    tool_resolved = Path(tool_root).resolve()
    if target_resolved == tool_resolved:
        return "refusing to initialize: <dir> is the tool's own repository"

    gen_dir = Path(target_dir) / "gen"
    tool_gen_dir = Path(tool_root) / "gen"
    if gen_dir.is_dir() and tool_gen_dir.is_dir():
        project_names = {p.name for p in gen_dir.iterdir() if p.is_dir()}
        tool_names = {p.name for p in tool_gen_dir.iterdir() if p.is_dir()}
        collisions = sorted(project_names & tool_names)
        if collisions:
            listed = ", ".join(f"gen/{name}" for name in collisions)
            return f"refusing: would shadow tool component(s): {listed}"
    return None


def _report(output_fn, rel_path, created):
    status = "created" if created else "skipped (exists)"
    output_fn(f"{rel_path}: {status}")


def _create_skeleton(target_dir, output_fn):
    for rel in _SKELETON_DIRS:
        p = target_dir / rel
        existed = p.exists()
        if not existed:
            p.mkdir(parents=True, exist_ok=True)
        _report(output_fn, rel, not existed)

    for rel in _GITKEEP_DIRS:
        p = target_dir / rel / ".gitkeep"
        existed = p.exists()
        if not existed:
            p.touch()
        _report(output_fn, f"{rel}/.gitkeep", not existed)

    glossary_path = target_dir / "specs" / "glossary.md"
    existed = glossary_path.exists()
    if not existed:
        glossary_path.write_text(
            "# Glossary\n\nCanonical vocabulary used by this project's specs.\n",
            encoding="utf-8",
        )
    _report(output_fn, "specs/glossary.md", not existed)

    allowlist_path = target_dir / ".secret-allowlist.json"
    existed = allowlist_path.exists()
    if not existed:
        content = json.dumps({"version": 1, "entries": []}, indent=2) + "\n"
        allowlist_path.write_bytes(content.encode("utf-8"))
    _report(output_fn, ".secret-allowlist.json", not existed)

    gitignore_path = target_dir / ".gitignore"
    existed = gitignore_path.exists()
    if not existed:
        gitignore_path.write_text("\n".join(_GITIGNORE_LINES) + "\n", encoding="utf-8")
    else:
        text = gitignore_path.read_text(encoding="utf-8")
        existing_lines = text.splitlines()
        to_append = [line for line in _GITIGNORE_LINES if line not in existing_lines]
        if to_append:
            sep = "" if (text == "" or text.endswith("\n")) else "\n"
            with gitignore_path.open("a", encoding="utf-8") as f:
                f.write(sep + "\n".join(to_append) + "\n")
    _report(output_fn, ".gitignore", not existed)


def _write_tool_marker(target_dir, tool_root):
    path = target_dir / ".hotdocs-tool.json"
    if not path.exists():
        content = json.dumps({"tool_version": TOOL_VERSION})
        path.write_text(content + "\n", encoding="utf-8")


def _copy_example(target_dir, tool_root):
    src_root = Path(tool_root) / "examples" / "slugify"
    if not src_root.exists():
        return
    for path in src_root.rglob("*"):
        if path.is_file():
            rel = path.relative_to(src_root)
            dest = target_dir / rel
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)


def _call_detect_providers(module, env_given):
    detect_providers = getattr(module, "detect_providers")
    if env_given is not None:
        return detect_providers(env=env_given)
    return detect_providers()


def _ask_with_default(input_fn, label, default, required):
    prompt = f"{label} [{default}]: " if default else f"{label}: "
    while True:
        answer = input_fn(prompt).strip()
        if answer:
            return answer
        if default:
            return default
        if not required:
            return None


def _ask_provider(detected_list, providers_table, input_fn, output_fn):
    if detected_list:
        output_fn("Available providers:")
        for idx, entry in enumerate(detected_list, start=1):
            name = _get(entry, "provider")
            available = _get(entry, "available")
            reason = _get(entry, "reason")
            if available:
                tag = "available"
            elif reason:
                tag = f"unavailable: {reason}"
            else:
                tag = "unavailable"
            output_fn(f"  {idx}. {name} ({tag})")
        available_names = [_get(e, "provider") for e in detected_list if _get(e, "available")]
        default = available_names[0] if available_names else _get(detected_list[0], "provider")
    else:
        names = list(providers_table.keys())
        output_fn("Available providers:")
        for idx, name in enumerate(names, start=1):
            output_fn(f"  {idx}. {name}")
        default = names[0] if names else None

    while True:
        answer = input_fn(f"Provider [{default}]: ").strip()
        if not answer:
            return default
        if answer in providers_table:
            return answer
        if answer.isdigit():
            idx = int(answer)
            if detected_list:
                if 1 <= idx <= len(detected_list):
                    return _get(detected_list[idx - 1], "provider")
            else:
                names = list(providers_table.keys())
                if 1 <= idx <= len(names):
                    return names[idx - 1]
        output_fn(f"unrecognised provider: {answer}")


def _save(target_dir, provider, model, base_url, api_key_env, module):
    save_config = getattr(module, "save_config")
    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key_env:
        kwargs["api_key_env"] = api_key_env
    try:
        save_config(Path(target_dir) / "hotdocs.toml", provider, model, **kwargs)
    except ValueError as e:
        print(f"could not save: {e}", file=sys.stderr)
        return False
    return True


def _run_test_and_save(*, target_dir, provider, model, base_url, api_key_env, opts, input_fn, output_fn, module, interactive):
    if opts.no_test:
        return _save(target_dir, provider, model, base_url, api_key_env, module)

    check_connection = getattr(module, "check_connection")
    try:
        conn = check_connection(provider, model, base_url=base_url, api_key_env=api_key_env)
        ok = _get(conn, "ok")
        error = _get(conn, "error")
    except ValueError as e:
        ok = False
        error = {"category": "invalid", "message": str(e)}

    if ok:
        output_fn("connection ok")
        return _save(target_dir, provider, model, base_url, api_key_env, module)

    category = _get(error, "category")
    message = _get(error, "message")
    output_fn(f"connection failed: {category}: {message}")

    if interactive:
        answer = input_fn("Save anyway? [y/N] ")
        if answer.strip().lower() == "y":
            return _save(target_dir, provider, model, base_url, api_key_env, module)
        return None

    output_fn("saving anyway")
    return _save(target_dir, provider, model, base_url, api_key_env, module)


def _configure_provider(*, target_dir, tool_root, opts, input_fn, output_fn, env_given, module):
    result = {"provider": None, "save_failed": False}
    if module is None:
        output_fn("provider not configured: gen/llm-endpoint is missing")
        return result

    providers_table = getattr(module, "PROVIDERS")
    interactive = opts.provider is None and not opts.yes

    if opts.provider is not None:
        provider = opts.provider
    elif opts.yes:
        detected_list = _call_detect_providers(module, env_given)
        available = [d for d in detected_list if _get(d, "available")]
        if not available:
            output_fn("no provider available: nothing configured")
            return result
        provider = _get(available[0], "provider")
    else:
        detected_list = _call_detect_providers(module, env_given)
        provider = _ask_provider(detected_list, providers_table, input_fn, output_fn)

    pinfo = providers_table[provider]

    model = opts.model
    if model is None:
        default_model = _get(pinfo, "suggested_model") or None
        if interactive:
            model = _ask_with_default(input_fn, "Model", default_model, required=True)
        else:
            model = default_model

    needs_base_url = _get(pinfo, "needs_base_url")
    base_url = opts.base_url
    if base_url is None and needs_base_url:
        default_base_url = _get(pinfo, "default_base_url")
        if interactive:
            base_url = _ask_with_default(input_fn, "Base URL", default_base_url, required=True)
        else:
            base_url = default_base_url

    api_key_env = opts.api_key_env
    if api_key_env is None and provider != "claude-cli":
        default_api_key_env = _get(pinfo, "default_api_key_env")
        if interactive:
            api_key_env = _ask_with_default(
                input_fn, "API key environment variable", default_api_key_env, required=False
            )
        else:
            api_key_env = default_api_key_env

    result["provider"] = provider

    saved = _run_test_and_save(
        target_dir=target_dir,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        opts=opts,
        input_fn=input_fn,
        output_fn=output_fn,
        module=module,
        interactive=interactive,
    )
    result["save_failed"] = saved is False
    return result


def _do_reconfigure(target_dir, tool_root, opts, input_fn, output_fn, env_given, module):
    if not (target_dir / "hotdocs.toml").exists():
        print(f"{target_dir}: not an initialised project", file=sys.stderr)
        return 1
    if module is None:
        print("gen/llm-endpoint is missing", file=sys.stderr)
        return 1

    result = _configure_provider(
        target_dir=target_dir,
        tool_root=tool_root,
        opts=opts,
        input_fn=input_fn,
        output_fn=output_fn,
        env_given=env_given,
        module=module,
    )
    if result.get("save_failed"):
        return 1
    return 0


def _check_prerequisites(tool_root_path, tool_root_arg, provider, env, output_fn):
    missing = False

    if sys.version_info < (3, 10):
        output_fn("missing: Python 3.10 or newer")
        output_fn("  fix: install Python 3.10 or newer")
        missing = True

    req_path = Path(tool_root_path) / "requirements.txt"
    if req_path.exists():
        for raw_line in req_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            name = line.split("==", 1)[0].strip()
            try:
                importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                output_fn(f"missing: {line}")
                output_fn(f"  fix: pip install -r {tool_root_arg}/requirements.txt")
                missing = True

    if provider == "claude-cli":
        path_value = env.get("PATH") if env is not None else None
        if shutil.which("claude", path=path_value) is None:
            output_fn("missing: claude on PATH")
            output_fn("  fix: install Claude Code and sign in")
            missing = True

    return missing


def _print_next_steps(example, output_fn):
    output_fn("Next steps:")
    output_fn("  hotdocs lint")
    if example:
        output_fn("  hotdocs generate comp-slugify")
    output_fn("  hotdocs verify")
    output_fn("  See QUICKSTART.md for more.")


def main(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None):
    input_fn = input_fn or input
    output_fn = output_fn or print
    env_given = env
    env = env if env is not None else os.environ
    cwd_path = Path(cwd) if cwd is not None else Path.cwd()
    tool_root_arg = tool_root
    tool_root_path = Path(tool_root)

    try:
        opts = _parse_args(argv)
    except UsageError as e:
        print(str(e), file=sys.stderr)
        return 2

    if opts.provider == "claude-cli" and (opts.base_url is not None or opts.api_key_env is not None):
        print("--base-url and --api-key-env are not valid with claude-cli", file=sys.stderr)
        return 2

    if opts.api_key_env is not None and not _API_KEY_ENV_RE.match(opts.api_key_env):
        print("--api-key-env must be a valid environment-variable name", file=sys.stderr)
        return 2

    target_dir = (cwd_path / opts.dir) if opts.dir else cwd_path

    refusal = _check_refusal(target_dir, tool_root_path)
    if refusal:
        print(refusal, file=sys.stderr)
        return 1

    module = _load_llm_endpoint(tool_root_path)

    if opts.provider is not None and module is not None:
        providers_table = getattr(module, "PROVIDERS")
        if opts.provider not in providers_table:
            keys = ", ".join(providers_table.keys())
            print(f"--provider must be one of: {keys}", file=sys.stderr)
            return 2
        pinfo = providers_table[opts.provider]
        if not _get(pinfo, "suggested_model") and opts.model is None:
            print(f"--provider {opts.provider} requires --model", file=sys.stderr)
            return 2
        if _get(pinfo, "needs_base_url") and opts.base_url is None:
            print(f"--provider {opts.provider} requires --base-url", file=sys.stderr)
            return 2

    if opts.reconfigure:
        return _do_reconfigure(target_dir, tool_root_path, opts, input_fn, output_fn, env_given, module)

    target_dir.mkdir(parents=True, exist_ok=True)

    _create_skeleton(target_dir, output_fn)
    _write_tool_marker(target_dir, tool_root_path)

    if opts.example:
        _copy_example(target_dir, tool_root_path)

    config_path = target_dir / "hotdocs.toml"
    provider_for_prereq = None
    if config_path.exists():
        output_fn("hotdocs.toml: skipped (exists)")
        if module is not None:
            load_config = getattr(module, "load_config")
            try:
                existing = load_config(config_path)
            except ValueError:
                existing = None
            if existing is not None:
                provider_for_prereq = _get(existing, "provider")
    else:
        result = _configure_provider(
            target_dir=target_dir,
            tool_root=tool_root_path,
            opts=opts,
            input_fn=input_fn,
            output_fn=output_fn,
            env_given=env_given,
            module=module,
        )
        provider_for_prereq = result.get("provider")

    missing = _check_prerequisites(tool_root_path, tool_root_arg, provider_for_prereq, env, output_fn)

    _print_next_steps(opts.example, output_fn)

    return 3 if missing else 0