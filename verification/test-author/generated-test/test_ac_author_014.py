"""AC-AUTHOR-014: the prompt author_test builds states that any list-valued
frontmatter field in a synthetic fixture must use flow-style syntax like
[a, b] rather than a dash-prefixed block list (R-AUTHOR-014)."""

import json
import re

import pytest

import test_author


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]{32})-----")
_HEX32_RE = re.compile(r"\b([0-9a-fA-F]{32})\b")


class _Bundle:
    """A CriterionBundle stand-in: exposes every documented field as an
    attribute and also reads as a mapping, as the real dataclass does."""

    _FIELDS = (
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
    )

    def __init__(self, **kwargs):
        self._data = {}
        for name in self._FIELDS:
            default = {} if name == "dependency_interfaces" else ""
            value = kwargs.get(name, default)
            self._data[name] = value
            setattr(self, name, value)
        if "module_names" in kwargs:
            self._data["module_names"] = kwargs["module_names"]
            setattr(self, "module_names", kwargs["module_names"])

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _bundles():
    # Deliberately free of the words/strings the assertions look for, so a
    # match can only come from author_test's own prompt text.
    return [
        _Bundle(
            component_id="comp-foo",
            criterion_id="AC-FOO-001",
            covers="R-FOO-001",
            criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
            requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
            interface="# Library\n\n```\nfoo(x: int) -> int\n```",
            glossary="# Glossary\n\n- **Foo** — a test term.",
            dependency_interfaces={},
        ),
        _Bundle(
            component_id="comp-bar",
            criterion_id="AC-BAR-002",
            covers="R-BAR-002",
            criterion_text="Given a name\nWhen bar(name) is called\nThen it returns a greeting",
            requirement_text="# R-BAR-002\n\n**R-BAR-002** — `bar(name)` MUST return `'hi ' + name`.",
            interface="# Library\n\n```\nbar(name: str) -> str\n```",
            glossary="# Glossary\n\n- **Bar** — another test term.",
            dependency_interfaces={
                "comp-foo": "# Library\n\n```\nfoo(x: int) -> int\n```",
            },
        ),
        _Bundle(
            component_id="comp-baz-qux",
            criterion_id="AC-BAZQUX-003",
            covers="R-BAZQUX-003",
            criterion_text="Given nothing\nWhen baz() is called\nThen it returns zero",
            requirement_text="# R-BAZQUX-003\n\n**R-BAZQUX-003** — `baz()` MUST return `0`.",
            interface="# Library\n\n```\nbaz() -> int\n```",
            glossary="# Glossary\n\n- **Baz** — a third test term.",
            dependency_interfaces={},
            module_names=["baz_qux"],
        ),
    ]


def _make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        m = _NONCE_RE.search(prompt)
        if m is None:
            m = _HEX32_RE.search(prompt)
        nonce = m.group(1) if m else "0" * 32
        body = "def test_placeholder():\n    assert True\n"
        text = (
            f"-----BEGIN FILE {nonce}-----\n"
            f"{body}"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _read_prompts(log_path):
    if not log_path.exists():
        return []
    prompts = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            prompts.append(json.loads(line)["prompt"])
    return prompts


@pytest.mark.parametrize("index", [0, 1, 2])
def test_prompt_requires_flow_style_frontmatter_lists(index, tmp_path, monkeypatch):
    bundle = _bundles()[index]

    # Sanity: the bundle itself carries none of the asserted text.
    for value in bundle.values():
        text = json.dumps(value) if not isinstance(value, str) else value
        assert "[a, b]" not in text
        assert "flow" not in text.lower()
        assert "block" not in text.lower()

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    log_path = tmp_path / "backend_calls.jsonl"
    backend = _make_backend(log_path)

    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=backend,
    )

    assert _field(result, "model_call_error") is None

    prompts = _read_prompts(log_path)
    assert prompts, "author_test never called the injected llm_backend"

    prompt = prompts[-1]
    assert isinstance(prompt, str)
    lowered = prompt.lower()

    # The literal flow-style example the requirement mandates.
    assert "[a, b]" in prompt, "prompt does not show the literal flow-style example [a, b]"
    # It names flow style and contrasts it with block style.
    assert "flow" in lowered, "prompt does not mention YAML flow style"
    assert "block" in lowered, "prompt does not rule out block-style lists"
    # The rule is about list-valued frontmatter fields in synthetic fixtures.
    assert "frontmatter" in lowered
    assert "list" in lowered
    assert "fixture" in lowered