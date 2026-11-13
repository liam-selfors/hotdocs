"""AC-GEN-001 (covers R-GEN-001).

Given a cold-mode SpecBundle and a mock model that records what it was sent,
when generate is called with that bundle, then the mock model's recorded input
contains exactly the bundle's spec, interface, constraints,
dependency_interfaces, vars, and glossary fields, and nothing else.

"Nothing else" is checked by planting distinctive tokens in every other
content source the generator could plausibly reach on its own: the on-disk
spec corpus (which deliberately differs from the bundle's own text), the
component's stale `gen/<component>/` content, a sibling component's `gen/`
content, a sealed dependency's real source, and the on-disk acceptance
criteria. None of those may reach the model. Only the bundle's six named
fields carry content into the prompt. The bundle's other fields
(`dependency_context`, `dependency_usage`) are left empty, and `hint_code` is
`None` (cold mode), so they contribute nothing either way.
"""

import dataclasses
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import generator


# ---------------------------------------------------------------------------
# A SpecBundle matching spec-bundle-assembler's documented shape: a dataclass
# with the documented fields in the documented order, which also reads as a
# mapping (bundle["spec"], bundle.get("spec")).
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class SpecBundle(dict):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __post_init__(self):
        dict.update(
            self,
            {f.name: getattr(self, f.name) for f in dataclasses.fields(self)},
        )


# ---------------------------------------------------------------------------
# Fake cache-manager. It matches the documented library contract and always
# reports a miss, so a real model call is guaranteed to happen.
# ---------------------------------------------------------------------------

FAKE_CACHE_MANAGER = r'''"""Fake cache-manager for AC-GEN-001: documented API, every get is a Miss."""
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

_REQUIRED_PAYLOAD_KEYS = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("cache_manager.Miss")

    def __repr__(self):
        return "Miss()"


class SchemaValidationError(ValueError):
    pass


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _has(obj, key):
    if isinstance(obj, dict):
        return key in obj
    return hasattr(obj, key)


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_version = _field(cache_key, "gate_version") or ""
    expected_type = str(gate_version).split("@", 1)[0]
    gate_type = _field(result, "gate_type")
    if gate_type not in _REQUIRED_PAYLOAD_KEYS or gate_type != expected_type:
        raise SchemaValidationError("gate_type does not match the cache key's gate_version")
    payload = _field(result, "payload")
    if payload is None:
        raise SchemaValidationError("missing payload")
    for key in _REQUIRED_PAYLOAD_KEYS[gate_type]:
        if not _has(payload, key):
            raise SchemaValidationError("payload missing required key: " + key)
    return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("inspect", "stats"):
        return 2
    cmd, rest = argv[0], argv[1:]
    known = {"--spec-bundle-hash", "--gate-inputs-hash", "--gate-version", "--model-pin", "--repo-root"}
    flags = {}
    i = 0
    while i < len(rest):
        tok = rest[i]
        if "=" in tok:
            name, val = tok.split("=", 1)
        else:
            name = tok
            if i + 1 >= len(rest):
                return 2
            i += 1
            val = rest[i]
        if name not in known:
            return 2
        flags[name] = val
        i += 1
    if cmd == "stats":
        if set(flags) - {"--repo-root"}:
            return 2
        print(json.dumps(stats()))
        return 0
    if not (known - {"--repo-root"}) <= set(flags):
        return 2
    print(json.dumps({"result": "miss"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

# Content that MUST reach the model: one token per bundle field.
INCLUDED_TOKENS = {
    "spec": ["QZXBUNDLESPECPURPOSEALPHA", "QZXBUNDLESPECREQBRAVO"],
    "interface": ["QZXBUNDLEINTERFACECHARLIE"],
    "constraints": ["QZXBUNDLECONSTRAINTSDELTA"],
    "dependency_interfaces": ["QZXBUNDLEDEPIFACEECHO"],
    "vars": ["QZXBUNDLEVARFOXTROT"],
    "glossary": ["QZXBUNDLEGLOSSARYGOLF"],
}

# Content that MUST NOT reach the model: it lives only outside the bundle.
EXCLUDED_TOKENS = {
    "stale gen/foo/ content (foo.py)": "WVKSTALEGENFOOPRIMARY",
    "stale gen/foo/ content (helper.py)": "WVKSTALEGENFOOHELPER",
    "sibling gen/bar/ content": "WVKSIBLINGGENBAR",
    "sealed dependency's real source": "WVKSEALEDLEGACYBAR",
    "on-disk component.md body": "WVKDISKCOMPONENTBODY",
    "on-disk requirements/ file": "WVKDISKREQUIREMENT",
    "on-disk acceptance/ file": "WVKDISKACCEPTANCE",
    "on-disk interface/ file": "WVKDISKINTERFACE",
    "on-disk constraints.md": "WVKDISKCONSTRAINTS",
    "on-disk dependency interface/": "WVKDISKDEPINTERFACE",
    "on-disk dependency Purpose": "WVKDISKDEPPURPOSE",
    "on-disk var declaration": "WVKDISKVARDECL",
    "on-disk glossary.md": "WVKDISKGLOSSARY",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_HEX32 = re.compile(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])")


def _find_nonce(prompt: str) -> str:
    for pattern in (r"BEGIN FILE ([0-9a-f]{32})", r"END FILE ([0-9a-f]{32})"):
        m = re.search(pattern, prompt)
        if m:
            return m.group(1)
    candidates = _HEX32.findall(prompt)
    if candidates:
        return candidates[0]
    return uuid.uuid4().hex


def _make_backend(log_path: Path):
    def backend(prompt, model, **params):
        record = {"prompt": prompt, "model": model, "params": params}
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=repr) + "\n")
        prompt_text = prompt if isinstance(prompt, str) else str(prompt)
        nonce = _find_nonce(prompt_text)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x: int) -> int:\n"
            "    return 2 * x\n"
            "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _build_repo(repo_root: Path) -> None:
    # The component under generation is NOT sealed: a sealed target would be
    # refused before any model call (R-GEN-009), so no prompt would exist.
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term. WVKDISKGLOSSARY\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: [comp-bar]\n"
        "uses_var: [VAR-FOO-URL]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number. WVKDISKCOMPONENTBODY\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`. WVKDISKREQUIREMENT\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2 WVKDISKACCEPTANCE\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "WVKDISKINTERFACE\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "constraints.md",
        "# Constraints\n"
        "\n"
        "None. WVKDISKCONSTRAINTS\n",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/bar/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Bar adds one. WVKDISKDEPPURPOSE\n",
    )
    _write(
        repo_root / "specs" / "components" / "bar" / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "bar(y: int) -> int\n"
        "```\n"
        "\n"
        "WVKDISKDEPINTERFACE\n",
    )
    _write(
        repo_root / "specs" / "vars" / "VAR-FOO-URL.md",
        "---\n"
        "id: VAR-FOO-URL\n"
        "title: Foo URL\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# VAR-FOO-URL\n"
        "\n"
        "The URL foo reads. WVKDISKVARDECL\n",
    )
    # Sealed dependency's real code: never generation input for comp-foo.
    _write(
        repo_root / "legacy" / "bar" / "bar.py",
        "# WVKSEALEDLEGACYBAR\n"
        "def bar(y):\n"
        "    return y + 1\n",
    )
    # The component's own current (stale) gen/ content: never cold-mode input.
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "# WVKSTALEGENFOOPRIMARY\n"
        "def foo(x):\n"
        "    return x * 3\n",
    )
    _write(
        repo_root / "gen" / "foo" / "helper.py",
        "# WVKSTALEGENFOOHELPER\n"
        "HELPER = 1\n",
    )
    # A sibling's generated code: never input either.
    _write(
        repo_root / "gen" / "bar" / "bar.py",
        "# WVKSIBLINGGENBAR\n"
        "def bar(y):\n"
        "    return y + 1\n",
    )
    # Fake cache-manager (flat-module shape): always a miss.
    _write(
        repo_root / "gen" / "cache-manager" / "cache_manager.py",
        FAKE_CACHE_MANAGER,
    )


def _build_bundle() -> SpecBundle:
    spec = (
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number. QZXBUNDLESPECPURPOSEALPHA\n"
        "\n"
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`. QZXBUNDLESPECREQBRAVO"
    )
    interface = (
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "QZXBUNDLEINTERFACECHARLIE"
    )
    constraints = "# Constraints\n\nNone. QZXBUNDLECONSTRAINTSDELTA"
    dependency_interfaces = {
        "comp-bar": (
            "# Library\n"
            "\n"
            "```\n"
            "bar(y: int) -> int\n"
            "```\n"
            "\n"
            "QZXBUNDLEDEPIFACEECHO"
        )
    }
    vars_ = {"VAR-FOO-URL": "# VAR-FOO-URL\n\nThe URL foo reads. QZXBUNDLEVARFOXTROT"}
    glossary = "# Glossary\n\n- **Foo** — a test term. QZXBUNDLEGLOSSARYGOLF"

    digest_source = json.dumps(
        {
            "spec": spec,
            "interface": interface,
            "constraints": constraints,
            "dependency_interfaces": dependency_interfaces,
            "vars": vars_,
            "glossary": glossary,
        },
        sort_keys=True,
    ).encode("utf-8")
    bundle_hash = "sha256:" + hashlib.sha256(digest_source).hexdigest()

    return SpecBundle(
        component_id="comp-foo",
        spec_bundle_hash=bundle_hash,
        spec=spec,
        interface=interface,
        constraints=constraints,
        dependency_interfaces=dependency_interfaces,
        dependency_context={},
        dependency_usage={},
        vars=vars_,
        glossary=glossary,
        hint_code=None,
    )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_ac_gen_001_cold_prompt_built_only_from_bundle_fields(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "model_calls.jsonl"
    backend = _make_backend(log_path)
    bundle = _build_bundle()

    result = None
    error = None
    try:
        result = generator.generate(
            bundle,
            "claude-sonnet-5",
            None,
            repo_root=repo_root,
            llm_backend=backend,
        )
    except Exception as exc:  # post-call failures belong to other criteria
        error = exc

    calls = []
    if log_path.is_file():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                calls.append(json.loads(line))

    assert calls, (
        "the mock model was never called for a cold-mode bundle; "
        f"refused={_read(result, 'refused')!r} "
        f"model_call_error={_read(result, 'model_call_error')!r} "
        f"cache_hit={_read(result, 'cache_hit')!r} exception={error!r}"
    )

    for index, call in enumerate(calls):
        prompt = call.get("prompt")
        prompt_text = prompt if isinstance(prompt, str) else json.dumps(prompt, default=repr)
        params_text = json.dumps(call.get("params", {}), default=repr)
        sent = prompt_text + "\n" + params_text

        for field_name, tokens in INCLUDED_TOKENS.items():
            for token in tokens:
                assert token in sent, (
                    f"model call #{index}: the bundle's `{field_name}` field "
                    f"content ({token}) is missing from what the model was sent"
                )

        for source, token in EXCLUDED_TOKENS.items():
            assert token not in sent, (
                f"model call #{index}: content from outside the bundle "
                f"({source}, {token}) reached the model"
            )