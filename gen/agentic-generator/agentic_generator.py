"""Agentic generation: the model works through tools inside a sandbox holding
only its spec bundle, writes and runs its own code and tests, and calls
`finish`; the result is a `generator` `GenerationResult`."""

import hashlib
import importlib.util
import json
import os
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

AGENT_PROMPT_VERSION = "agent-v1"
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
BWRAP = "bwrap"

_CUT = 8192
_MAX_BYTES = 524288
_MAX_FILES = 200
_RUN_SECONDS = 60

_PROFILE = """(version 1)
(allow default)
(deny network*)
(deny file-write*)
(allow file-write* (subpath (param "ROOT")) (literal "/dev/null"))
(deny file-read-data (subpath (param "REPO")))
(allow file-read-data (subpath (param "PREFIX")) (subpath (param "ROOT")))
"""

_TOOLS = [
    ("list_files",
     "List every file at any depth under a directory, one path per line, "
     "each relative to the sandbox root (ready to pass to read_file).",
     {"path": "A directory relative to the sandbox root, e.g. bundle"}),
    ("read_file",
     "Read a file's content as UTF-8 text.",
     {"path": "A file relative to the sandbox root, e.g. bundle/01-spec.md"}),
    ("write_file",
     "Write a file under work/ or scratch/, creating parent directories.",
     {"path": "A file relative to the sandbox root under work/ or scratch/",
      "content": "The complete file content"}),
    ("delete_file",
     "Delete a file under work/ or scratch/.",
     {"path": "A file relative to the sandbox root under work/ or scratch/"}),
    ("check_import",
     "Import the component's module from work/; returns the exit code and output.",
     {}),
    ("run_scratch_tests",
     "Run pytest over scratch/ with work/ importable; returns the exit code and output.",
     {}),
    ("finish",
     "Finish: everything under work/ becomes the candidate. Call once, when done.",
     {"summary": "A short summary of what you built"}),
]
_ARGS = {name: tuple(props) for name, _desc, props in _TOOLS}
_READ_ROOTS = ("bundle", "work", "scratch")
_WRITE_ROOTS = ("work", "scratch")


def _field(obj, name):
    if isinstance(obj, dict):
        return obj[name]
    return getattr(obj, name)


def _tool_root():
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load(base, slug, modname):
    directory = base / "gen" / slug
    if not directory.is_dir():
        directory = _tool_root() / "gen" / slug
    path = directory / (modname + ".py")
    spec = importlib.util.spec_from_file_location(modname, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


def _os_sandbox():
    if sys.platform == "darwin" and os.path.exists(SANDBOX_EXEC):
        return "sandbox-exec"
    if sys.platform.startswith("linux") and shutil.which(BWRAP):
        return "bwrap"
    return None


def _isolation_level(allow_unisolated_exec):
    level = _os_sandbox()
    if level is not None:
        return level
    return "unisolated" if allow_unisolated_exec else "none"


def _slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _cut(text):
    if len(text) > _CUT:
        return text[:_CUT] + "\n[truncated]"
    return text


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))


def _allowed(root, path, roots):
    if not path or os.path.isabs(path):
        return False
    parts = path.split("/")
    if ".." in parts or parts[0] not in roots:
        return False
    for i in range(1, len(parts) + 1):
        if os.path.islink(os.path.join(root, *parts[:i])):
            return False
    real = os.path.realpath(os.path.join(root, path))
    return real.startswith(root + os.sep)


def _count_files(root):
    total = 0
    for top in _WRITE_ROOTS:
        for _dirpath, _dirnames, filenames in os.walk(os.path.join(root, top)):
            total += len(filenames)
    return total


def _system_text(module):
    return (
        "You are a developer writing the code for one software component, "
        "working inside a sandbox directory. The sandbox holds exactly these "
        "directories:\n"
        "- bundle/: the component's spec bundle, read-only.\n"
        f"- work/: your only output. It must hold `{module}.py` or "
        f"`{module}/__init__.py` (plus any other files the component needs). "
        "Everything under work/ when you finish is the candidate.\n"
        "- scratch/: your own tests, run by run_scratch_tests. It is "
        "discarded and never kept.\n"
        "- tmp/: the temporary directory and home of code you run.\n"
        "You have no other access: no network, no repository, nothing outside "
        "this sandbox. Read the bundle, write the module under work/, check "
        "that it imports with check_import, write tests under scratch/ and run "
        "them with run_scratch_tests, and revise until it is right. Call the "
        "tool `finish` when you are done."
    )


def _prompt_text(names, module):
    listing = "\n".join(f"- {name}" for name in names)
    return (
        "Your spec bundle is in these files, in order:\n"
        f"{listing}\n\n"
        "Read them all before writing anything. Then write the component as "
        f"`work/{module}.py` or `work/{module}/__init__.py`, test it under "
        "scratch/, and call `finish` when done."
    )


def generate_agentic(bundle, model, retry_feedback=None, *, repo_root: Path = None,
                     allow_unisolated_exec: bool = False, max_turns: int = 40,
                     max_tool_calls: int = 120, wall_seconds: float = 1800.0,
                     claude_command: str = "claude"):
    repo_dir = Path(repo_root) if repo_root is not None else _tool_root()
    gen = _load(repo_dir, "generator", "generator")
    component_id = bundle["component_id"]

    def result(**fields):
        base = dict(
            component_id=component_id,
            spec_bundle_hash=bundle["spec_bundle_hash"],
            model=model,
            prompt_version=AGENT_PROMPT_VERSION,
            cache_hit=False,
            files={},
            model_call_error=None,
            refused=None,
            retry_feedback=retry_feedback,
            mode="agentic",
            transcript_sha256=None,
            turns=0,
            tool_calls=0,
            isolation=_isolation_level(allow_unisolated_exec),
        )
        base.update(fields)
        return gen.GenerationResult(**base)

    reason = gen.check_write_allowed(bundle, repo_root)
    if reason:
        return result(refused=reason)

    module = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    module = module.replace("-", "_")
    sections = gen.render_prompt_sections(bundle, retry_feedback)
    tool_loop = _load(repo_dir, "llm-tool-endpoint", "llm_tool_endpoint")

    root = os.path.realpath(tempfile.mkdtemp(prefix="hotdocs-agent-"))
    profile_path = root + ".sb"
    bundle_dir = os.path.join(root, "bundle")
    work_dir = os.path.join(root, "work")
    tmp_dir = os.path.join(root, "tmp")
    try:
        os.mkdir(bundle_dir)
        names = []
        for position, (title, text) in enumerate(sections, start=1):
            filename = f"{position:02d}-{_slugify(title)}.md"
            file_path = os.path.join(bundle_dir, filename)
            with open(file_path, "wb") as handle:
                handle.write(text.encode("utf-8"))
            os.chmod(file_path, 0o444)
            names.append("bundle/" + filename)
        os.chmod(bundle_dir, 0o555)
        os.mkdir(work_dir)
        os.mkdir(os.path.join(root, "scratch"))
        os.mkdir(tmp_dir)

        state = {"finished": False, "isolation": None}
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": tmp_dir,
            "TMPDIR": tmp_dir,
            "PYTHONPATH": work_dir,
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        def run(command):
            level = _os_sandbox()
            if level is None and not allow_unisolated_exec:
                return "no OS sandbox available: code is not run", True
            state["isolation"] = level or "unisolated"
            if level == "sandbox-exec":
                with open(profile_path, "w", encoding="utf-8") as handle:
                    handle.write(_PROFILE)
                argv = [SANDBOX_EXEC, "-f", profile_path,
                        "-D", f"ROOT={root}",
                        "-D", f"REPO={os.path.realpath(repo_dir)}",
                        "-D", f"PREFIX={os.path.realpath(sys.prefix)}"] + command
            elif level == "bwrap":
                repo_real = os.path.realpath(repo_dir)
                prefix = os.path.realpath(sys.prefix)
                argv = [shutil.which(BWRAP), "--ro-bind", "/", "/",
                        "--tmpfs", repo_real,
                        "--ro-bind", prefix, prefix,
                        "--bind", root, root,
                        "--dev", "/dev", "--proc", "/proc",
                        "--unshare-net", "--die-with-parent",
                        "--chdir", root, "--"] + command
            else:
                argv = command
            proc = subprocess.Popen(argv, cwd=root, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, preexec_fn=_limits,
                                    start_new_session=True)
            try:
                out, _ = proc.communicate(timeout=_RUN_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                out, _ = proc.communicate()
                return "timeout\n" + out.decode("utf-8", "replace"), False
            return f"{proc.returncode}\n{out.decode('utf-8', 'replace')}", False

        def call(name, arguments):
            if state["finished"]:
                return "already finished", True
            if name not in _ARGS:
                return f"bad call: unknown tool {name}", True
            args = arguments if isinstance(arguments, dict) else {}
            for arg in _ARGS[name]:
                if not isinstance(args.get(arg), str):
                    return f"bad call: missing {arg}", True
            if name == "finish":
                state["finished"] = True
                return "finished", False
            if name == "check_import":
                return run([sys.executable, "-c", f"import {module}"])
            if name == "run_scratch_tests":
                return run([sys.executable, "-m", "pytest", "-q", "-p",
                            "no:cacheprovider", "--noconftest", "scratch"])
            path = args["path"]
            roots = _WRITE_ROOTS if name in ("write_file", "delete_file") else _READ_ROOTS
            if not _allowed(root, path, roots):
                return f"path not allowed: {path}", True
            full = os.path.join(root, path)
            if name == "list_files":
                if not os.path.isdir(full):
                    return f"not found: {path}", True
                found = []
                for dirpath, _dirnames, filenames in os.walk(full):
                    for filename in filenames:
                        rel = os.path.relpath(os.path.join(dirpath, filename), root)
                        found.append(rel.replace(os.sep, "/"))
                return "\n".join(sorted(found)), False
            if name == "read_file":
                if not os.path.isfile(full):
                    return f"not found: {path}", True
                with open(full, "rb") as handle:
                    return handle.read().decode("utf-8", "replace"), False
            if name == "write_file":
                data = args["content"].encode("utf-8")
                if len(data) > _MAX_BYTES:
                    return f"too large: {path} is {len(data)} bytes, limit {_MAX_BYTES}", True
                if not os.path.exists(full) and _count_files(root) + 1 > _MAX_FILES:
                    return f"too many files: limit {_MAX_FILES}", True
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "wb") as handle:
                    handle.write(data)
                return f"wrote {path}", False
            if not os.path.isfile(full):
                return f"not found: {path}", True
            os.remove(full)
            return f"deleted {path}", False

        def execute(name, arguments):
            try:
                text, is_error = call(name, arguments)
            except OSError as exc:
                text, is_error = f"{name} failed: {exc}", True
            return _cut(text), is_error

        tools = [
            {
                "name": name,
                "description": description,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        arg: {"type": "string", "description": text}
                        for arg, text in props.items()
                    },
                    "required": list(props),
                },
            }
            for name, description, props in _TOOLS
        ]

        loop = tool_loop.run_tool_loop(
            _system_text(module), _prompt_text(names, module), model, tools, execute,
            max_turns=max_turns, max_tool_calls=max_tool_calls,
            wall_seconds=wall_seconds, repo_root=repo_root,
            claude_command=claude_command,
        )

        transcript = _field(loop, "transcript")
        digest = hashlib.sha256(
            json.dumps(transcript, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        common = dict(
            transcript_sha256="sha256:" + digest,
            turns=_field(loop, "turns"),
            tool_calls=_field(loop, "tool_calls"),
            isolation=state["isolation"] or _isolation_level(allow_unisolated_exec),
        )

        if not state["finished"]:
            stop = _field(loop, "stop")
            if stop == "error":
                error = _field(loop, "model_call_error")
            elif stop == "budget_exhausted":
                error = {"category": "agent_budget_exhausted",
                         "message": f"agent stopped before finish: {stop}"}
            else:
                error = {"category": "agent_unfinished",
                         "message": f"agent stopped before finish: {stop}"}
            return result(model_call_error=error, **common)

        files = {}
        for dirpath, dirnames, filenames in os.walk(work_dir):
            dirnames.sort()
            for filename in sorted(filenames):
                full = os.path.join(dirpath, filename)
                if not stat.S_ISREG(os.lstat(full).st_mode):
                    continue
                rel = os.path.relpath(full, work_dir).replace(os.sep, "/")
                with open(full, "rb") as handle:
                    data = handle.read()
                try:
                    files[rel] = data.decode("utf-8")
                except UnicodeDecodeError:
                    return result(model_call_error={
                        "category": "undecodable_file",
                        "message": f"work/{rel} is not valid UTF-8",
                    }, **common)

        if f"{module}.py" not in files and f"{module}/__init__.py" not in files:
            return result(model_call_error={
                "category": "missing_module",
                "message": f"work/ holds neither {module}.py nor {module}/__init__.py",
            }, **common)

        if bundle["hint_code"] is None:
            gen.write_files(component_id, files, repo_root=repo_root)
        return result(files=files, **common)
    finally:
        if os.path.isdir(bundle_dir):
            os.chmod(bundle_dir, 0o755)
        shutil.rmtree(root, ignore_errors=True)
        if os.path.exists(profile_path):
            os.remove(profile_path)
