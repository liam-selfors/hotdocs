"""Agentic generation: the model works through tools in a sandbox holding
only its spec bundle, until it calls ``finish``."""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

AGENT_PROMPT_VERSION = "agent-v2"
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
BWRAP = "bwrap"

_CUT = 8192
_MAX_BYTES = 524288
_MAX_FILES = 200
_RUN_SECONDS = 60
_NO_SANDBOX = "no OS sandbox available: code is not run"

_PROFILE = """(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (subpath (param "ROOT")) (literal "/dev/null"))
(deny file-read-data (subpath (param "REPO")))
(allow file-read-data (subpath (param "PREFIX")) (subpath (param "ROOT")))
"""

_TOOLS = [
    ("list_files", ["path"],
     "List every file at any depth under the directory `path`, one per line, "
     "each as its path relative to the sandbox root."),
    ("read_file", ["path"], "Read the file at `path` as UTF-8 text."),
    ("write_file", ["path", "content"],
     "Write `content` to the file at `path` under work/ or scratch/, making parent directories."),
    ("delete_file", ["path"], "Delete the file at `path` under work/ or scratch/."),
    ("check_import", [], "Import the component's module from work/; returns the exit code and output."),
    ("run_scratch_tests", [], "Run pytest over scratch/; returns the exit code and output."),
    ("finish", ["summary"], "Call when the component in work/ is done."),
]
_ARGS = {name: args for name, args, _ in _TOOLS}


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    here = Path(__file__).resolve()
    return next(p for p in here.parents if p.name == "gen").parent


def _load(slug, module, repo_root):
    base = None
    if repo_root is not None:
        cand = Path(repo_root) / "gen" / slug
        if cand.is_dir():
            base = cand
    if base is None:
        base = _tool_root() / "gen" / slug
    path = base / f"{module}.py"
    name = f"_agentic_generator_dep_{module}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _declared_assets(repo, slug):
    path = Path(repo) / "specs" / "components" / slug / "component.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines))
        lines = lines[1:end]
    for line in lines:
        if line.startswith("assets:"):
            inner = line[line.index("[") + 1:line.index("]")]
            items = [i.strip() for i in inner.split(",") if i.strip()]
            return [i.split(":", 1)[1].strip() for i in items]
    return []


def _isolation(allow):
    if sys.platform == "darwin" and os.path.exists(SANDBOX_EXEC):
        return "sandbox-exec"
    if sys.platform.startswith("linux") and shutil.which(BWRAP):
        return "bwrap"
    return "unisolated" if allow else "none"


def _limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))


def _cut(text):
    if len(text) > _CUT:
        return text[:_CUT] + "\n[truncated]"
    return text


def generate_agentic(bundle, model, retry_feedback=None, *, repo_root=None,
                     allow_unisolated_exec=False, max_turns=40, max_tool_calls=120,
                     wall_seconds=1800.0, claude_command="claude"):
    gen = _load("generator", "generator", repo_root)
    component_id = bundle["component_id"]
    spec_hash = bundle["spec_bundle_hash"]

    def result(**kw):
        fields = dict(
            component_id=component_id, spec_bundle_hash=spec_hash, model=model,
            prompt_version=AGENT_PROMPT_VERSION, cache_hit=False, files={},
            model_call_error=None, refused=None, retry_feedback=retry_feedback,
            mode="agentic", transcript_sha256=None, turns=0, tool_calls=0,
            isolation=_isolation(allow_unisolated_exec),
        )
        fields.update(kw)
        return gen.GenerationResult(**fields)

    reason = gen.check_write_allowed(bundle, repo_root)
    if reason:
        return result(refused=reason)
    category, messages = gen.check_asset_environment(component_id, repo_root)
    if category:
        return result(model_call_error={"category": category, "message": "\n".join(messages)})

    loop_mod = _load("llm-tool-endpoint", "llm_tool_endpoint", repo_root)
    repo = Path(repo_root) if repo_root is not None else _tool_root()
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    module = slug.replace("-", "_")
    assets = _declared_assets(repo, slug)

    root = os.path.realpath(tempfile.mkdtemp(prefix="hotdocs-agent-"))
    profile = root + ".sb"
    try:
        bundle_dir = os.path.join(root, "bundle")
        for d in ("bundle", "work", "scratch", "tmp"):
            os.mkdir(os.path.join(root, d))
        names = []
        sections = gen.render_prompt_sections(bundle, retry_feedback)
        for i, (title, text) in enumerate(sections, start=1):
            fname = f"{i:02d}-{_slugify(title)}.md"
            fpath = os.path.join(bundle_dir, fname)
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.chmod(fpath, 0o444)
            names.append(f"bundle/{fname}")
        os.chmod(bundle_dir, 0o555)

        state = {"finished": False, "isolation": None}

        def resolve(path, writable):
            bad = (f"path not allowed: {path}", True)
            if path == "" or path.startswith("/") or os.path.isabs(path):
                return None, bad
            parts = path.split("/")
            if ".." in parts:
                return None, bad
            allowed = ("work", "scratch") if writable else ("bundle", "work", "scratch")
            if parts[0] not in allowed:
                return None, bad
            cur = root
            for part in parts:
                cur = os.path.join(cur, part)
                if os.path.islink(cur):
                    return None, bad
            target = os.path.join(root, *parts)
            real = os.path.realpath(target)
            if real != root and not real.startswith(root + os.sep):
                return None, bad
            return target, None

        def count_files():
            n = 0
            for d in ("work", "scratch"):
                for _, _, files in os.walk(os.path.join(root, d)):
                    n += len(files)
            return n

        def run(cmd):
            level = _isolation(allow_unisolated_exec)
            if level == "none":
                return _NO_SANDBOX, True
            if level == "sandbox-exec":
                with open(profile, "w", encoding="utf-8") as fh:
                    fh.write(_PROFILE)
                full = [SANDBOX_EXEC, "-f", profile, "-D", f"ROOT={root}",
                        "-D", f"REPO={os.path.realpath(str(repo))}",
                        "-D", f"PREFIX={os.path.realpath(sys.prefix)}", *cmd]
            elif level == "bwrap":
                rp = os.path.realpath(str(repo))
                prefix = os.path.realpath(sys.prefix)
                full = [shutil.which(BWRAP), "--ro-bind", "/", "/", "--tmpfs", rp,
                        "--ro-bind", prefix, prefix, "--bind", root, root,
                        "--dev", "/dev", "--proc", "/proc", "--unshare-net",
                        "--die-with-parent", "--chdir", root, "--", *cmd]
            else:
                full = list(cmd)
            env = {
                "PATH": "/usr/bin:/bin",
                "HOME": os.path.join(root, "tmp"),
                "TMPDIR": os.path.join(root, "tmp"),
                "PYTHONPATH": os.path.join(root, "work"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            state["isolation"] = level
            proc = subprocess.Popen(full, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    preexec_fn=_limits)
            try:
                out, _ = proc.communicate(timeout=_RUN_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, _ = proc.communicate()
                return "timeout\n" + out.decode("utf-8", errors="replace"), False
            return f"{proc.returncode}\n" + out.decode("utf-8", errors="replace"), False

        def dispatch(name, arguments):
            if state["finished"]:
                return "already finished", True
            if name not in _ARGS:
                return f"bad call: unknown tool {name}", True
            for arg in _ARGS[name]:
                if not (isinstance(arguments, dict) and isinstance(arguments.get(arg), str)):
                    return f"bad call: missing {arg}", True
            try:
                if name == "finish":
                    state["finished"] = True
                    return "finished", False
                if name == "check_import":
                    return run([sys.executable, "-c", f"import {module}"])
                if name == "run_scratch_tests":
                    return run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                "--noconftest", "scratch"])
                path = arguments["path"]
                target, err = resolve(path, name in ("write_file", "delete_file"))
                if err:
                    return err
                if name == "list_files":
                    if not os.path.isdir(target):
                        return f"not found: {path}", True
                    found = []
                    for dirpath, _, files in os.walk(target):
                        for f in files:
                            rel = os.path.relpath(os.path.join(dirpath, f), root)
                            found.append(rel.replace(os.sep, "/"))
                    return "\n".join(sorted(found)), False
                if name == "read_file":
                    if not os.path.isfile(target):
                        return f"not found: {path}", True
                    with open(target, "rb") as fh:
                        return fh.read().decode("utf-8", errors="replace"), False
                if name == "write_file":
                    data = arguments["content"].encode("utf-8")
                    if len(data) > _MAX_BYTES:
                        return f"too large: {path} is {len(data)} bytes, limit {_MAX_BYTES}", True
                    if not os.path.exists(target) and count_files() + 1 > _MAX_FILES:
                        return f"too many files: limit {_MAX_FILES}", True
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as fh:
                        fh.write(data)
                    return f"wrote {path}", False
                # delete_file
                if not os.path.isfile(target):
                    return f"not found: {path}", True
                os.remove(target)
                return f"deleted {path}", False
            except Exception as exc:  # execute never raises
                return f"{name} failed: {exc}", True

        def execute(name, arguments):
            text, is_error = dispatch(name, arguments)
            return _cut(text), is_error

        tools = [
            {
                "name": name,
                "description": desc,
                "input_schema": {
                    "type": "object",
                    "properties": {a: {"type": "string"} for a in args},
                    "required": list(args),
                },
            }
            for name, args, desc in _TOOLS
        ]

        asset_text = ""
        if assets:
            asset_text = ", plus each declared asset file: " + ", ".join(assets)
        system = "\n".join([
            "You are generating one software component inside a sandbox directory. "
            "Every tool path is relative to the sandbox root and written with /.",
            "The sandbox holds exactly these directories:",
            "- bundle/: the component's spec bundle, read-only.",
            f"- work/: your only output. It must hold {module}.py or {module}/__init__.py"
            f"{asset_text}, and no other non-.py file.",
            "- scratch/: your own tests, run with run_scratch_tests. It is discarded.",
            "- tmp/: the HOME and TMPDIR of code you run.",
            "You have no other access: no network, no repository, nothing outside this sandbox.",
            "When the component is done, call the tool finish.",
        ])
        prompt = "\n".join(
            ["Your spec bundle is these files, in order:"]
            + [f"- {n}" for n in names]
            + ["Read them all with read_file before writing anything. Then write the "
               f"component into work/, check it with check_import, write tests in scratch/ "
               "and run them with run_scratch_tests, revise until they pass, and call finish."]
        )

        loop = loop_mod.run_tool_loop(
            system, prompt, model, tools, execute,
            max_turns=max_turns, max_tool_calls=max_tool_calls,
            wall_seconds=wall_seconds, repo_root=repo_root,
            claude_command=claude_command,
        )
        transcript = _get(loop, "transcript")
        digest = hashlib.sha256(
            json.dumps(transcript, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        common = dict(
            turns=_get(loop, "turns"),
            tool_calls=_get(loop, "tool_calls"),
            transcript_sha256="sha256:" + digest,
            isolation=state["isolation"] or _isolation(allow_unisolated_exec),
        )

        if not state["finished"]:
            stop = _get(loop, "stop")
            if stop == "error":
                error = _get(loop, "model_call_error")
            elif stop == "budget_exhausted":
                error = {"category": "agent_budget_exhausted",
                         "message": "tool loop stopped before finish: budget_exhausted"}
            else:
                error = {"category": "agent_unfinished",
                         "message": f"tool loop stopped before finish: {stop}"}
            return result(model_call_error=error, **common)

        work = os.path.join(root, "work")
        candidate = {}
        for dirpath, _, files in os.walk(work):
            for f in files:
                full = os.path.join(dirpath, f)
                if os.path.islink(full) or not os.path.isfile(full):
                    continue
                rel = os.path.relpath(full, work).replace(os.sep, "/")
                with open(full, "rb") as fh:
                    raw = fh.read()
                try:
                    candidate[rel] = raw.decode("utf-8")
                except UnicodeDecodeError:
                    return result(model_call_error={
                        "category": "undecodable_file",
                        "message": f"work/{rel} is not valid UTF-8"}, **common)
        if f"{module}.py" not in candidate and f"{module}/__init__.py" not in candidate:
            return result(model_call_error={
                "category": "missing_module",
                "message": f"work/ holds neither {module}.py nor {module}/__init__.py"}, **common)
        category, messages = gen.check_assets(component_id, candidate, repo_root=repo_root)
        if category:
            return result(model_call_error={"category": category,
                                            "message": "\n".join(messages)}, **common)
        if bundle["hint_code"] is None:
            gen.write_files(component_id, candidate, repo_root=repo_root)
        return result(files=candidate, **common)
    finally:
        bundle_dir = os.path.join(root, "bundle")
        if os.path.isdir(bundle_dir):
            os.chmod(bundle_dir, 0o755)
        shutil.rmtree(root, ignore_errors=True)
        if os.path.exists(profile):
            os.remove(profile)
