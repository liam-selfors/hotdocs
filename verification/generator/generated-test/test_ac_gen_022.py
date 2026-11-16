import json
import re
import uuid
from dataclasses import dataclass, field, fields as dc_fields
from pathlib import Path

import generator


@dataclass
class FakeSpecBundle:
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

    def __getitem__(self, key):
        if key in {f.name for f in dc_fields(self)}:
            return getattr(self, key)
        raise KeyError(key)

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


def _write_fixture(repo_root: Path) -> None:
    (repo_root / "specs" / "components" / "foo" / "requirements").mkdir(parents=True)
    (repo_root / "specs" / "components" / "foo" / "acceptance").mkdir(parents=True)
    (repo_root / "specs" / "components" / "foo" / "interface").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )
    (repo_root / "specs" / "components" / "foo" / "component.md").write_text(
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
        encoding="utf-8",
    )
    (repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
        encoding="utf-8",
    )
    (repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
        encoding="utf-8",
    )
    (repo_root / "specs" / "components" / "foo" / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (repo_root / "specs" / "components" / "foo" / "constraints.md").write_text(
        "# Constraints\n\nNone.\n", encoding="utf-8"
    )


_NONCE_IN_MARKER = re.compile(r"BEGIN FILE\s+([0-9a-f]{32})")
_ANY_NONCE = re.compile(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])")


def test_ac_gen_022_prompt_says_nothing_more_and_mutation_testing(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    work_dir = tmp_path / "cwd"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    log_path = tmp_path / "mock_prompts.jsonl"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        text_prompt = prompt if isinstance(prompt, str) else str(prompt)
        m = _NONCE_IN_MARKER.search(text_prompt)
        if m:
            nonce = m.group(1)
        else:
            m2 = _ANY_NONCE.search(text_prompt)
            nonce = m2.group(1) if m2 else uuid.uuid4().hex
        reply = (
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": reply,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )

    result = generator.generate(
        bundle,
        "mock-model",
        None,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    cache_hit = result.get("cache_hit") if isinstance(result, dict) else getattr(result, "cache_hit", None)
    refused = result.get("refused") if isinstance(result, dict) else getattr(result, "refused", None)
    assert refused in (None, ""), f"generation unexpectedly refused: {refused!r}"
    assert not cache_hit, "expected a fresh model call, got a cache hit"

    assert log_path.is_file(), "the mock model was never called"
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records, "the mock model was never called"

    prompts = [r["prompt"] if isinstance(r["prompt"], str) else str(r["prompt"]) for r in records]
    for prompt in prompts:
        lowered = prompt.lower()
        assert "nothing more" in lowered, "prompt lacks 'nothing more'"
        assert "mutation testing" in lowered, "prompt lacks 'mutation testing'"