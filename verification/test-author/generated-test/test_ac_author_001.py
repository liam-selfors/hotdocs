import re

import test_author


CRITERION_TEXT = (
    "Given a zebra-quartz widget named QX-7781\n"
    "When frobnicate_qx7781 is invoked\n"
    "Then it returns the string marigold-teapot-5521"
)
REQUIREMENT_TEXT = (
    "**R-FOO-001** \u2014 `frobnicate_qx7781()` MUST return the sentinel "
    "string `marigold-teapot-5521` (requirement-sentinel-90417)."
)
INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "frobnicate_qx7781() -> str  # interface-sentinel-33820\n"
    "```"
)
GLOSSARY_TEXT = (
    "# Glossary\n"
    "\n"
    "- **Quartzling** \u2014 a glossary-sentinel-61294 test term."
)


class Bundle:
    """A CriterionBundle stand-in readable both by attribute and as a mapping."""

    _FIELDS = (
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
        "module_names",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._FIELDS:
            return getattr(self, key)
        return default

    def __contains__(self, key):
        return key in self._FIELDS

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def keys(self):
        return list(self._FIELDS)

    def items(self):
        return [(k, getattr(self, k)) for k in self._FIELDS]

    def values(self):
        return [getattr(self, k) for k in self._FIELDS]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_author_001_prompt_contains_criterion_requirement_interface_glossary(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    bundle = Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=CRITERION_TEXT,
        requirement_text=REQUIREMENT_TEXT,
        interface=INTERFACE_TEXT,
        glossary=GLOSSARY_TEXT,
        dependency_interfaces={},
        module_names=["foo"],
    )

    recorded = []
    log_path = tmp_path / "mock_calls.log"

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-fA-F]+)-----", prompt)
        nonce = match.group(1) if match else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_placeholder():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = test_author.author_test(
        bundle,
        "anthropic:claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert field(result, "model_call_error") is None
    assert log_path.is_file(), "mock model was never called"
    assert len(recorded) >= 1

    sent = "\n".join(recorded)

    assert CRITERION_TEXT in sent, "criterion text missing from model input"
    assert REQUIREMENT_TEXT in sent, "requirement text missing from model input"
    assert INTERFACE_TEXT in sent, "interface missing from model input"
    assert GLOSSARY_TEXT in sent, "glossary missing from model input"