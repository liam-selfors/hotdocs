"""AC-GEN-017 (covers R-GEN-016).

In hint mode (bundle.hint_code is not None), generate() MUST NOT write to
gen/<component>/ or to cache-manager; it returns the candidate (or cache hit)
in the GenerationResult only. Reading the cache is unaffected.
"""

import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

import generator


COMPONENT_ID = "comp-foo"
SLUG = "foo"
MODEL = "claude-sonnet-5"

ORIGINAL_GEN_FILES = {
    "foo.py": "# ORIGINAL VERIFIED CODE - must never be overwritten by a hint preview\n"
              "def foo(x):\n"
              "    return x + x\n",
    "helpers/util.py": "# original helper\nVALUE = 1\n",
}

CANDIDATE_PATH = "foo.py"
CANDIDATE_CONTENT = "def foo(x):\n    return 2 * x  # hint-mode candidate\n"

CACHED_FILES = {"foo.py": "def foo(x):\n    return 2 * x  # cached cold-mode result\n"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot(directory: Path):
    """Map of every file/dir under `directory` (relative) to its bytes (or a dir marker)."""
    snap = {}
    if not directory.exists():
        return snap
    for root, dirs, files in os.walk(directory):
        root_path = Path(root)
        for d in dirs:
            snap[str((root_path / d).relative_to(directory)) + "/"] = b"<dir>"
        for f in files:
            p = root_path / f
            snap[str(p.relative_to(directory))] = p.read_bytes()
    return snap


def _files_under(directory: Path):
    if not directory.exists():
        return []
    return [p for p in directory.rglob("*") if p.is_file()]


def _read_jsonl(path: Path):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _gate_inputs_hash(retry_feedback):
    payload = json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


FAKE_CACHE_MANAGER_TEMPLATE = '''\
import dataclasses
import datetime
import json
import typing

_LOG = {log_path!r}
_STORE = {store_path!r}


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash("Miss")

    def __repr__(self):
        return "Miss()"


class SchemaValidationError(ValueError):
    pass


_REQUIRED = {{
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}}


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _key(cache_key):
    out = []
    for n in ("spec_bundle_hash", "gate_inputs_hash", "gate_version", "model_pin"):
        v = _get(cache_key, n)
        out.append(v if v is None else str(v))
    return out


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\\n")


def _load():
    try:
        with open(_STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(cache_key, *, repo_root=None):
    key = _key(cache_key)
    _log({{"op": "get", "key": key}})
    for entry in _load():
        if entry.get("key") == key:
            r = entry["result"]
            return CachedResult(
                gate_type=r["gate_type"], payload=r["payload"], stored_at=r["stored_at"]
            )
    return Miss()


def put(cache_key, result, *, repo_root=None):
    key = _key(cache_key)
    _log({{"op": "put", "key": key, "result": result}})
    gate_version = _get(cache_key, "gate_version") or ""
    gate_type = str(gate_version).split("@", 1)[0]
    r_type = _get(result, "gate_type")
    payload = _get(result, "payload")
    if r_type != gate_type or r_type not in _REQUIRED or not isinstance(payload, dict):
        raise SchemaValidationError("gate_type mismatch or unknown")
    for k in _REQUIRED[r_type]:
        if k not in payload:
            raise SchemaValidationError("missing payload key: " + k)
    entries = [e for e in _load() if e.get("key") != key]
    entries.append({{
        "key": key,
        "result": {{"gate_type": r_type, "payload": payload,
                    "stored_at": _get(result, "stored_at")}},
    }})
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(entries, f, default=str)
    return None


def stats(*, repo_root=None):
    return {{"entry_count": len(_load())}}


def main(argv=None):
    return 0
'''


@dataclasses.dataclass
class _LocalSpecBundle:
    """Stand-in mirroring spec-bundle-assembler's documented SpecBundle contract:
    a dataclass with these fields in this order that also reads as a read-only mapping."""
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: dict = None

    def __getitem__(self, key):
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self.keys():
            return getattr(self, key)
        return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __contains__(self, key):
        return key in self.keys()

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]

    def values(self):
        return [getattr(self, k) for k in self.keys()]


def _real_spec_bundle_class():
    try:
        gen_dir = next(
            p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
        )
        base = gen_dir / "spec-bundle-assembler"
        flat = base / "spec_bundle_assembler.py"
        path = flat if flat.is_file() else base / "spec_bundle_assembler" / "__init__.py"
        if not path.is_file():
            return None
        module_name = "spec_bundle_assembler"
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # register BEFORE exec_module
        spec.loader.exec_module(module)
        return getattr(module, "SpecBundle", None)
    except Exception:
        return None


def _make_bundle(spec_bundle_hash: str, hint_code: dict):
    kwargs = dict(
        component_id=COMPONENT_ID,
        spec_bundle_hash=spec_bundle_hash,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
             "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Foo** — a test term.",
        hint_code=dict(hint_code),
    )
    cls = _real_spec_bundle_class()
    if cls is not None:
        try:
            bundle = cls(**kwargs)
            hc = _field(bundle, "hint_code")
            if hc is not None and _field(bundle, "spec_bundle_hash") == spec_bundle_hash:
                return bundle
        except Exception:
            pass
    return _LocalSpecBundle(**kwargs)


def _build_repo(tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    control = tmp_path / "control"
    control.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    # Minimal spec corpus for comp-foo (non-sealed, so generation is not refused).
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp_dir = repo_root / "specs" / "components" / SLUG
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(comp_dir / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # Existing, "verified" gen/<component>/ contents.
    gen_component = repo_root / "gen" / SLUG
    for rel, content in ORIGINAL_GEN_FILES.items():
        _write(gen_component / rel, content)

    # Fake cache-manager dependency (flat-module shape) that logs every call.
    cache_log = control / "cache_calls.jsonl"
    cache_store = control / "cache_store.json"
    cache_store.write_text("[]", encoding="utf-8")
    _write(
        repo_root / "gen" / "cache-manager" / "cache_manager.py",
        FAKE_CACHE_MANAGER_TEMPLATE.format(
            log_path=str(cache_log), store_path=str(cache_store)
        ),
    )

    return repo_root, control, cwd, gen_component, cache_log, cache_store


_NONCE_IN_MARKER = re.compile(r"BEGIN FILE ([0-9a-f]{32})\b")
_STANDALONE_NONCE = re.compile(r"(?<![0-9A-Za-z])([0-9a-f]{32})(?![0-9A-Za-z])")


def _make_mock_model(log_path: Path):
    def mock_backend(prompt, model, **params):
        text_prompt = prompt if isinstance(prompt, str) else str(prompt)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"model": str(model), "prompt_len": len(text_prompt)}) + "\n")
        nonces = list(dict.fromkeys(_NONCE_IN_MARKER.findall(text_prompt)))
        if not nonces:
            nonces = list(dict.fromkeys(_STANDALONE_NONCE.findall(text_prompt)))
        blocks = []
        for n in nonces:
            blocks.append(
                f"-----BEGIN FILE {n}: {CANDIDATE_PATH}-----\n"
                f"{CANDIDATE_CONTENT}"
                f"-----END FILE {n}-----\n"
            )
        return {
            "text": "Here is the file.\n" + "".join(blocks),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return mock_backend


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root, control, cwd, gen_component, cache_log, cache_store = _build_repo(tmp_path)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(cwd)
    return {
        "repo_root": repo_root,
        "control": control,
        "cwd": cwd,
        "gen_component": gen_component,
        "cache_log": cache_log,
        "cache_store": cache_store,
        "model_log": control / "model_calls.jsonl",
    }


def _assert_no_real_local_cache_writes(env):
    for base in (env["repo_root"], env["cwd"]):
        written = _files_under(base / ".hotdocs" / "cache")
        assert written == [], f"cache was written under {base}: {written}"


# ---------------------------------------------------------------------------
# Scenario 1: hint mode, cache miss -> candidate returned, nothing written
# ---------------------------------------------------------------------------

def test_hint_mode_miss_returns_candidate_without_writing_gen_or_cache(env):
    spec_hash = "sha256:" + hashlib.sha256(b"ac-gen-017-scenario-1").hexdigest()
    bundle = _make_bundle(spec_hash, ORIGINAL_GEN_FILES)
    assert _field(bundle, "hint_code") is not None

    before = _snapshot(env["gen_component"])
    mock = _make_mock_model(env["model_log"])

    result = generator.generate(
        bundle, MODEL, None, repo_root=env["repo_root"], llm_backend=mock
    )

    # The mock model was actually called.
    assert len(_read_jsonl(env["model_log"])) >= 1

    # The result carries the candidate's files.
    assert _field(result, "model_call_error") is None
    assert _field(result, "refused") is None
    assert _field(result, "cache_hit") is False
    files = _field(result, "files")
    assert isinstance(files, dict) and files, f"expected non-empty files, got {files!r}"
    assert CANDIDATE_PATH in files
    assert files[CANDIDATE_PATH].strip() == CANDIDATE_CONTENT.strip()
    assert _field(result, "component_id") == COMPONENT_ID
    assert _field(result, "spec_bundle_hash") == spec_hash

    # gen/<component>/ is untouched.
    after = _snapshot(env["gen_component"])
    assert after == before, "gen/<component>/ was modified in hint mode"
    assert (env["gen_component"] / "foo.py").read_text(encoding="utf-8") == ORIGINAL_GEN_FILES["foo.py"]

    # Nothing written to the cache.
    puts = [r for r in _read_jsonl(env["cache_log"]) if r.get("op") == "put"]
    assert puts == [], f"cache-manager.put was called in hint mode: {puts}"
    assert json.loads(env["cache_store"].read_text(encoding="utf-8")) == []
    _assert_no_real_local_cache_writes(env)


# ---------------------------------------------------------------------------
# Scenario 2: hint mode, existing cold-mode cache entry -> cache hit, no model call
# ---------------------------------------------------------------------------

def test_hint_mode_cache_hit_returns_cached_result_without_model_call_or_writes(env):
    spec_hash = "sha256:" + hashlib.sha256(b"ac-gen-017-scenario-2").hexdigest()
    gate_version = getattr(generator, "GATE_VERSION", "generator@2.0.0")
    prompt_version = getattr(generator, "PROMPT_VERSION", "v10")

    key = [spec_hash, _gate_inputs_hash(None), gate_version, MODEL]
    cached_payload = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": spec_hash,
        "model": MODEL,
        "prompt_version": prompt_version,
        "cache_hit": False,
        "files": dict(CACHED_FILES),
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    env["cache_store"].write_text(
        json.dumps([{
            "key": key,
            "result": {
                "gate_type": gate_version.split("@", 1)[0],
                "payload": cached_payload,
                "stored_at": "2026-10-02T00:00:00Z",
            },
        }]),
        encoding="utf-8",
    )
    store_before = env["cache_store"].read_text(encoding="utf-8")

    bundle = _make_bundle(spec_hash, ORIGINAL_GEN_FILES)
    assert _field(bundle, "hint_code") is not None

    before = _snapshot(env["gen_component"])
    mock = _make_mock_model(env["model_log"])

    result = generator.generate(
        bundle, MODEL, None, repo_root=env["repo_root"], llm_backend=mock
    )

    # No model call occurred.
    assert _read_jsonl(env["model_log"]) == [], "model was called despite a cache hit"

    # The cache was read, and the cached result is returned.
    gets = [r for r in _read_jsonl(env["cache_log"]) if r.get("op") == "get"]
    assert gets, "cache-manager.get was never called in hint mode"
    assert _field(result, "cache_hit") is True
    assert _field(result, "model_call_error") is None
    assert _field(result, "refused") is None
    files = _field(result, "files")
    assert isinstance(files, dict)
    assert {k: v.strip() for k, v in files.items()} == {
        k: v.strip() for k, v in CACHED_FILES.items()
    }
    assert _field(result, "component_id") == COMPONENT_ID

    # gen/<component>/ stays untouched.
    after = _snapshot(env["gen_component"])
    assert after == before, "gen/<component>/ was modified in hint mode"

    # Nothing written to the cache.
    puts = [r for r in _read_jsonl(env["cache_log"]) if r.get("op") == "put"]
    assert puts == [], f"cache-manager.put was called in hint mode: {puts}"
    assert env["cache_store"].read_text(encoding="utf-8") == store_before
    _assert_no_real_local_cache_writes(env)