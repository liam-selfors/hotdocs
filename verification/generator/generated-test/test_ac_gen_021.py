import json
import os
import re
import secrets
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import generator


@dataclass
class _FakeSpecBundle(Mapping):
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

    def _names(self):
        return [
            "component_id",
            "spec_bundle_hash",
            "spec",
            "interface",
            "constraints",
            "dependency_interfaces",
            "dependency_context",
            "dependency_usage",
            "vars",
            "glossary",
            "hint_code",
        ]

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _extract_nonce(prompt):
    m = re.findall(r"BEGIN FILE\s+([0-9a-f]{32})\b", prompt)
    if m:
        return max(set(m), key=m.count)
    candidates = re.findall(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])", prompt)
    assert candidates, "prompt does not state a 32-hex nonce"
    return max(set(candidates), key=candidates.count)


FILES = {
    "foo-bar/foo_bar.py": "def foo_bar():\n    return 1\n",
    "gen/foo-bar/helpers/__init__.py": "HELPER = 2\n",
    "foo_bar_extra.py": "EXTRA = 3\n",
}


def _write_component_md(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo-bar"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo-bar\n"
        "title: Foo Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo bar returns one.\n",
        encoding="utf-8",
    )


def test_ac_gen_021_strips_one_redundant_leading_component_prefix(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component_md(repo_root)

    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    log_path = tmp_path / "backend_calls.log"

    def mock_backend(prompt, model, **params):
        nonce = _extract_nonce(prompt)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model, "nonce": nonce}) + "\n")
        parts = []
        for path, content in FILES.items():
            parts.append(f"-----BEGIN FILE {nonce}: {path}-----")
            parts.append(content.rstrip("\n"))
            parts.append(f"-----END FILE {nonce}-----")
        return {
            "text": "\n".join(parts) + "\n",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    unique = secrets.token_hex(16)
    bundle = _FakeSpecBundle(
        component_id="comp-foo-bar",
        spec_bundle_hash="sha256:" + hashlib.sha256(unique.encode("utf-8")).hexdigest(),
        spec="# Foo Bar\n\n## Purpose\n\nFoo bar returns one.\n\n# R-FOO-BAR-001\n\n**R-FOO-BAR-001** — `foo_bar()` MUST return `1`.",
        interface="# Library\n\n```\nfoo_bar() -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert log_path.is_file(), "mock backend was never invoked"
    assert _field(result, "model_call_error") is None, _field(result, "model_call_error")
    assert _field(result, "refused") is None, _field(result, "refused")
    assert _field(result, "files"), "expected non-empty files"

    out = repo_root / "gen" / "foo-bar"
    expected = {
        out / "foo_bar.py": FILES["foo-bar/foo_bar.py"],
        out / "helpers" / "__init__.py": FILES["gen/foo-bar/helpers/__init__.py"],
        out / "foo_bar_extra.py": FILES["foo_bar_extra.py"],
    }
    for path, content in expected.items():
        assert path.is_file(), f"missing {path}"
        assert path.read_text(encoding="utf-8").strip() == content.strip()

    assert not (out / "foo-bar").exists(), "nothing may be written under gen/foo-bar/foo-bar/"
    assert not (out / "gen").exists(), "nothing may be written under gen/foo-bar/gen/"