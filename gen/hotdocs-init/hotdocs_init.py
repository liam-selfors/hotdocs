import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

TOOL_VERSION = "0.1.0"

_BOOL_FLAGS = {"--example", "--reconfigure", "--no-test", "--yes"}
_VALUE_FLAGS = {"--provider", "--model", "--base-url", "--api-key-env"}

_SECRET_ALLOWLIST_ENTRY = {
    "file": "gen/review-packet-builder/review_packet_builder.py",
    "type": "Hex High Entropy String",
    "hashed_secret": "sha1:2c74b2b5a39b54beae7d7c0e994feb84693a3466",
    "reason": "public-constant",
}


class UsageError(Exception):
    pass


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _load_module_from_path(path, module_name):
    if not path.is_file():
        return None
    old_dont_write = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old_dont_write
    return module


def _load_tool_llm_endpoint(tool_root_path):
    path = tool_root_path / "gen" / "llm-endpoint" / "llm_endpoint.py"
    return _load_module_from_path(path, "hotdocs_init_tool_llm_endpoint")


def _load_project_llm_endpoint(dir_path):
    path = dir_path / "gen" / "llm-endpoint" / "llm_endpoint.py"
    return _load_module_from_path(path, "hotdocs_init_project_llm_endpoint")


def _parse_args(argv, tool_root_path):
    args = {
        "dir": None,
        "example": False,
        "reconfigure": False,
        "provider": None,
        "model": None,
        "base_url": None,
        "api_key_env": None,
        "no_test": False,
        "yes": False,
    }
    positionals = []
    i = 0
    n = len(argv)
    while i < n:
        tok = argv[i]
        if tok.startswith("--"):
            if "=" in tok:
                flag, val = tok.split("=", 1)
            else:
                flag, val = tok, None
            if flag in _BOOL_FLAGS:
                if val is not None:
                    raise UsageError(f"unknown flag: {tok}")
                key = flag[2:].replace("-", "_")
                args[key] = True
                i += 1
            elif flag in _VALUE_FLAGS:
                key = flag[2:].replace("-", "_")
                if val is None:
                    if i + 1 >= n:
                        raise UsageError(f"{flag} requires a value")
                    val = argv[i + 1]
                    i += 2
                else:
                    i += 1
                args[key] = val
            else:
                raise UsageError(f"unknown flag: {tok}")
        else:
            positionals.append(tok)
            i += 1

    if len(positionals) > 1:
        raise UsageError("unexpected extra argument")
    if positionals:
        args["dir"] = positionals[0]

    module = _load_tool_llm_endpoint(tool_root_path)
    providers_dict = getattr(module, "PROVIDERS", {}) if module is not None else {}

    if args["provider"] is not None:
        if args["provider"] not in providers_dict:
            keys = ", ".join(sorted(providers_dict.keys()))
            raise UsageError(f"unknown provider '{args['provider']}'; must be one of: {keys}")
        info = providers_dict[args["provider"]]
        if args["provider"] == "claude-cli":
            if args["base_url"] is not None or args["api_key_env"] is not None:
                raise UsageError("--base-url and --api-key-env are not valid with claude-cli")
        suggested_model = _get(info, "suggested_model")
        if not suggested_model and args["model"] is None:
            raise UsageError(f"--provider {args['provider']} has no suggested model; --model is required")
        needs_base_url = _get(info, "needs_base_url")
        if needs_base_url and args["base_url"] is None:
            raise UsageError(f"--provider {args['provider']} requires --base-url")

    if args["api_key_env"] is not None:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", args["api_key_env"]):
            raise UsageError("--api-key-env is not a valid environment-variable name")

    return args


def _same_path(a, b):
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return os.path.abspath(str(a)) == os.path.abspath(str(b))


def _walk_files_skip_pycache(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            yield Path(dirpath) / fn


def _copy_tree_skip_pycache(src, dest):
    dest.mkdir(parents=True, exist_ok=True)
    for entry in sorted(src.iterdir()):
        if entry.name == "__pycache__":
            continue
        target = dest / entry.name
        if entry.is_dir():
            _copy_tree_skip_pycache(entry, target)
        else:
            shutil.copy2(entry, target)


def _vendor_targets(tool_root_path):
    targets = []
    gen_dir = tool_root_path / "gen"
    if gen_dir.is_dir():
        for child in sorted(gen_dir.iterdir()):
            if child.is_dir() and child.name != "__pycache__":
                targets.append((f"gen/{child.name}", child))
    cc_src = tool_root_path / "pipeline" / "criterion-compiler"
    if cc_src.is_dir():
        targets.append(("pipeline/criterion-compiler", cc_src))
    return targets


def _read_stamp(dir_path):
    stamp_path = dir_path / ".hotdocs-tool.json"
    if not stamp_path.exists():
        return None
    try:
        return json.loads(stamp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _find_vendor_collisions(dir_path, tool_root_path):
    stamp = _read_stamp(dir_path)
    vendored_in_stamp = set(_get(stamp, "vendored", []) or []) if stamp else set()
    collisions = []
    for rel, _src in _vendor_targets(tool_root_path):
        target = dir_path / rel
        if target.exists() and rel not in vendored_in_stamp:
            collisions.append(rel)
    return collisions


def _create_skeleton(dir_path, output_fn):
    def report(rel, created):
        output_fn(f"{rel}: created" if created else f"{rel}: skipped (exists)")

    dirs = ["specs/product", "specs/components", "specs/decisions", "gen", "pipeline", "verification"]
    for d in dirs:
        p = dir_path / d
        existed = p.exists()
        p.mkdir(parents=True, exist_ok=True)
        report(d, not existed)

    gitkeep_dirs = ["specs/product", "specs/components", "specs/decisions", "verification"]
    for d in gitkeep_dirs:
        p = dir_path / d / ".gitkeep"
        rel = f"{d}/.gitkeep"
        if p.exists():
            report(rel, False)
        else:
            p.touch()
            report(rel, True)

    glossary_path = dir_path / "specs" / "glossary.md"
    if glossary_path.exists():
        report("specs/glossary.md", False)
    else:
        glossary_path.write_text(
            "# Glossary\n\n"
            "This file holds the canonical vocabulary used across this project's specs.\n",
            encoding="utf-8",
        )
        report("specs/glossary.md", True)

    _create_secret_allowlist(dir_path, report)
    _update_gitignore(dir_path, report)


def _create_secret_allowlist(dir_path, report):
    path = dir_path / ".secret-allowlist.json"
    if path.exists():
        report(".secret-allowlist.json", False)
        return

    doc = {"version": 1, "entries": [_SECRET_ALLOWLIST_ENTRY]}
    content = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    path.write_bytes(content)
    report(".secret-allowlist.json", True)

    digest = hashlib.sha256(content).hexdigest()
    decisions_dir = dir_path / "specs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    existing_ns = []
    for p in decisions_dir.glob("D*.md"):
        m = re.match(r"^D(\d+)\.md$", p.name)
        if m:
            existing_ns.append(int(m.group(1)))
    next_n = max(existing_ns, default=0) + 1
    decision_path = decisions_dir / f"D{next_n}.md"
    decision_content = (
        "---\n"
        f"id: D{next_n}\n"
        "title: Seal the initial secret allowlist\n"
        "status: ratified\n"
        "owners: [project]\n"
        "last_ratified_commit: hotdocs-init\n"
        f"allowlist_sha256: sha256:{digest}\n"
        "---\n\n"
        f"# D{next_n}\n\n"
        "This allowlist changes only through a new decision that records its new hash.\n"
    )
    decision_path.write_text(decision_content, encoding="utf-8")
    report(f"specs/decisions/D{next_n}.md", True)


def _update_gitignore(dir_path, report):
    path = dir_path / ".gitignore"
    required_lines = ["/.hotdocs/", "__pycache__/", "*.pyc", ".venv/"]
    existed = path.exists()
    if existed:
        existing_lines = path.read_text(encoding="utf-8").splitlines()
    else:
        existing_lines = []
    to_add = [line for line in required_lines if line not in existing_lines]
    if to_add:
        with path.open("a", encoding="utf-8") as f:
            for line in to_add:
                f.write(line + "\n")
    report(".gitignore", not existed)


def _vendor(dir_path, tool_root_path, output_fn):
    stamp = _read_stamp(dir_path)
    vendored_in_stamp = set(_get(stamp, "vendored", []) or []) if stamp else set()
    targets = _vendor_targets(tool_root_path)

    for rel, src in targets:
        dest = dir_path / rel
        if rel in vendored_in_stamp or dest.exists():
            output_fn(f"{rel}: skipped (exists)")
            continue
        _copy_tree_skip_pycache(src, dest)
        output_fn(f"{rel}: created")

    if stamp is not None:
        output_fn(".hotdocs-tool.json: skipped (exists)")
        return

    file_entries = []
    for rel, _src in targets:
        dest = dir_path / rel
        if not dest.exists():
            continue
        for f in _walk_files_skip_pycache(dest):
            relf = f.relative_to(dir_path).as_posix()
            file_entries.append((relf, f.read_bytes()))
    file_entries.sort(key=lambda x: x[0])

    hasher = hashlib.sha256()
    for relf, data in file_entries:
        hasher.update(relf.encode("utf-8"))
        hasher.update(data)
    content_hash = "sha256:" + hasher.hexdigest()

    vendored_list = sorted(rel for rel, _ in targets if (dir_path / rel).exists())
    stamp_doc = {
        "tool_version": TOOL_VERSION,
        "vendored": vendored_list,
        "content_hash": content_hash,
    }
    (dir_path / ".hotdocs-tool.json").write_text(
        json.dumps(stamp_doc, indent=2) + "\n", encoding="utf-8"
    )
    output_fn(".hotdocs-tool.json: created")


def _copy_example(dir_path, tool_root_path, output_fn):
    src_root = tool_root_path / "examples" / "slugify"
    if not src_root.is_dir():
        return
    for f in sorted(_walk_files_skip_pycache(src_root)):
        rel = f.relative_to(src_root)
        dest = dir_path / rel
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)


def _ask_interactively(detected, providers_dict, input_fn, output_fn):
    output_fn("Available providers:")
    for idx, d in enumerate(detected, start=1):
        name = _get(d, "provider")
        avail = _get(d, "available")
        marker = "" if avail else " (unavailable)"
        output_fn(f"  {idx}. {name}{marker}")

    available = [d for d in detected if _get(d, "available")]
    if available:
        default_provider = _get(available[0], "provider")
    elif detected:
        default_provider = _get(detected[0], "provider")
    else:
        default_provider = None

    name_to_entry = {_get(d, "provider"): d for d in detected}

    while True:
        ans = input_fn(f"Provider [{default_provider}]: ").strip()
        if not ans:
            provider = default_provider
            break
        if ans in providers_dict:
            provider = ans
            break
        if ans.isdigit():
            idx = int(ans)
            if 1 <= idx <= len(detected):
                provider = _get(detected[idx - 1], "provider")
                break
        output_fn(f"unrecognised provider: {ans}")

    entry = name_to_entry.get(provider)
    info = providers_dict[provider]

    default_model = (_get(entry, "suggested_model") if entry else None) or _get(info, "suggested_model")
    while True:
        ans = input_fn(f"Model [{default_model}]: ").strip()
        if ans:
            model = ans
            break
        if default_model:
            model = default_model
            break
        output_fn("a model is required")

    base_url = None
    if _get(info, "needs_base_url"):
        default_base_url = _get(info, "default_base_url")
        while True:
            ans = input_fn(f"Base URL [{default_base_url}]: ").strip()
            if ans:
                base_url = ans
                break
            if default_base_url:
                base_url = default_base_url
                break
            output_fn("a base URL is required")

    api_key_env = None
    if provider != "claude-cli":
        default_api_key_env = (_get(entry, "api_key_env") if entry else None) or _get(
            info, "default_api_key_env"
        )
        ans = input_fn(f"API key environment variable [{default_api_key_env or ''}]: ").strip()
        api_key_env = ans or default_api_key_env or None

    return provider, model, base_url, api_key_env


def _configure_provider(args, dir_path, input_fn, output_fn, env_given, effective_env):
    status = {"provider": None, "missing_endpoint": False, "save_error": None, "saved": False}

    module = _load_project_llm_endpoint(dir_path)
    if module is None:
        status["missing_endpoint"] = True
        return status

    providers_dict = getattr(module, "PROVIDERS")
    detect = getattr(module, "detect_providers")
    check_connection = getattr(module, "check_connection")
    save_config = getattr(module, "save_config")

    if args["provider"]:
        provider = args["provider"]
        info = providers_dict[provider]
        model = args["model"] or _get(info, "suggested_model")
        if provider == "claude-cli":
            base_url = None
            api_key_env = None
        else:
            base_url = (
                args["base_url"]
                if args["base_url"] is not None
                else (_get(info, "default_base_url") if _get(info, "needs_base_url") else None)
            )
            api_key_env = (
                args["api_key_env"] if args["api_key_env"] is not None else _get(info, "default_api_key_env")
            )
    elif args["yes"]:
        detected = detect(env=effective_env) if env_given else detect()
        available = [d for d in detected if _get(d, "available")]
        if not available:
            output_fn("no provider available; provider not configured")
            return status
        chosen = available[0]
        provider = _get(chosen, "provider")
        info = providers_dict[provider]
        model = _get(chosen, "suggested_model") or _get(info, "suggested_model")
        if provider == "claude-cli":
            base_url = None
            api_key_env = None
        else:
            base_url = _get(info, "default_base_url") if _get(info, "needs_base_url") else None
            api_key_env = _get(chosen, "api_key_env") or _get(info, "default_api_key_env")
    else:
        detected = detect(env=effective_env) if env_given else detect()
        provider, model, base_url, api_key_env = _ask_interactively(
            detected, providers_dict, input_fn, output_fn
        )

    status["provider"] = provider

    do_save = True
    if not args["no_test"]:
        try:
            result = check_connection(provider, model, base_url=base_url, api_key_env=api_key_env)
            ok = _get(result, "ok")
            error = _get(result, "error")
        except ValueError as e:
            ok = False
            error = {"category": "invalid", "message": str(e)}
        if ok:
            output_fn("connection ok")
        else:
            category = _get(error, "category")
            message = _get(error, "message")
            output_fn(f"connection failed: {category}: {message}")
            if args["yes"] or args["provider"]:
                output_fn("warning: saving despite failed connection")
                do_save = True
            else:
                answer = input_fn("Save anyway? [y/N] ")
                do_save = answer.strip().lower().startswith("y")

    if do_save:
        try:
            kwargs = {}
            if base_url:
                kwargs["base_url"] = base_url
            if api_key_env:
                kwargs["api_key_env"] = api_key_env
            save_config(dir_path / "hotdocs.toml", provider, model, **kwargs)
            status["saved"] = True
        except ValueError as e:
            print(f"could not save: {e}", file=sys.stderr)
            status["save_error"] = str(e)

    return status


def _load_configured_provider(dir_path):
    module = _load_project_llm_endpoint(dir_path)
    if module is None:
        return None
    try:
        cfg = module.load_config(dir_path / "hotdocs.toml")
    except ValueError:
        return None
    if cfg is None:
        return None
    return _get(cfg, "provider")


def _check_prerequisites(dir_path, tool_root, tool_root_path, effective_env, chosen_provider, output_fn):
    missing = False

    if sys.version_info < (3, 10):
        output_fn("missing: Python 3.10 or newer")
        output_fn("  fix: install Python 3.10 or newer")
        missing = True

    req_path = tool_root_path / "requirements.txt"
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
                output_fn(f"  fix: pip install -r {tool_root}/requirements.txt")
                missing = True

    if chosen_provider == "claude-cli":
        if shutil.which("claude", path=effective_env.get("PATH")) is None:
            output_fn("missing: claude on PATH")
            output_fn("  fix: install Claude Code and sign in")
            missing = True

    return missing


def _print_next_steps(example, output_fn):
    output_fn("next steps:")
    output_fn("  hotdocs lint")
    if example:
        output_fn("  hotdocs generate comp-slugify")
    output_fn("  hotdocs verify")
    output_fn("  see QUICKSTART.md")


def _run_reconfigure(args, dir_path, input_fn, output_fn, env_given, effective_env):
    if not (dir_path / ".hotdocs-tool.json").exists():
        print(f"refusing: {dir_path} is not an initialised project", file=sys.stderr)
        return 1

    status = _configure_provider(args, dir_path, input_fn, output_fn, env_given, effective_env)

    if status["missing_endpoint"]:
        print("provider not configured: gen/llm-endpoint is missing", file=sys.stderr)
        return 1
    if status["save_error"]:
        return 1
    return 0


def main(argv, *, tool_root, input_fn=None, output_fn=None, env=None, cwd=None):
    input_fn = input_fn if input_fn is not None else input
    output_fn = output_fn if output_fn is not None else print
    env_given = env is not None
    effective_env = env if env is not None else os.environ
    cwd_path = Path(cwd) if cwd is not None else Path.cwd()
    tool_root_path = Path(tool_root)

    try:
        args = _parse_args(list(argv), tool_root_path)
    except UsageError as e:
        print(str(e), file=sys.stderr)
        return 2

    dir_arg = args["dir"]
    dir_path = (cwd_path / dir_arg) if dir_arg else cwd_path

    if args["reconfigure"]:
        return _run_reconfigure(args, dir_path, input_fn, output_fn, env_given, effective_env)

    if _same_path(dir_path, tool_root_path):
        print(f"refusing: {dir_path} is the tool's own repository", file=sys.stderr)
        return 1

    collisions = _find_vendor_collisions(dir_path, tool_root_path)
    if collisions:
        for c in collisions:
            print(f"refusing: {c} already exists", file=sys.stderr)
        return 1

    dir_path.mkdir(parents=True, exist_ok=True)

    _create_skeleton(dir_path, output_fn)
    _vendor(dir_path, tool_root_path, output_fn)

    toml_path = dir_path / "hotdocs.toml"
    if toml_path.exists():
        output_fn("hotdocs.toml: skipped (exists)")
        chosen_provider = _load_configured_provider(dir_path)
    else:
        status = _configure_provider(args, dir_path, input_fn, output_fn, env_given, effective_env)
        if status["missing_endpoint"]:
            output_fn("provider not configured: gen/llm-endpoint is missing")
        chosen_provider = status["provider"]

    if args["example"]:
        _copy_example(dir_path, tool_root_path, output_fn)

    missing = _check_prerequisites(
        dir_path, tool_root, tool_root_path, effective_env, chosen_provider, output_fn
    )

    _print_next_steps(args["example"], output_fn)

    return 3 if missing else 0