import json
import re
import uuid
from dataclasses import dataclass, field as dc_field, fields as dc_fields
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class FakeSpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [f.name for f in dc_fields(self)]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        return key in self.keys()

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]

    def values(self):
        return [getattr(self, k) for k in self.keys()]


def _make_bundle():
    return FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
            "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def test_ac_gen_022_prompt_says_nothing_more_and_mutation_testing(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "mock_prompts.jsonl"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = match.group(1) if match else uuid.uuid4().hex
        text = (
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            f"-----END FILE {nonce}-----\n"
            f"-----END REPLY {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _make_bundle()
    result = generator.generate(
        bundle,
        "mock:model",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )
    assert result is not None
    assert field(result, "cache_hit") is False

    assert log_path.is_file(), "mock model was never called"
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records, "mock model was never called"

    for record in records:
        prompt = record["prompt"]
        assert isinstance(prompt, str)
        assert "nothing more" in prompt
        assert "mutation testing" in prompt