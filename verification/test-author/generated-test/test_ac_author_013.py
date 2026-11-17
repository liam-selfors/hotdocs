import re

import test_author


EXPECTED_LINE = (
    "- Only a criterion that needs `realizes`-driven behavior has the "
    "fixture supply a resolvable `P-<id>`."
)


class _Bundle:
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
            setattr(self, name, kwargs[name])

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


def _make_bundle():
    return _Bundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=(
            "Given x = 2\n"
            "When make_widget(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** — `make_widget(x)` MUST return `2 * x`.\n"
        ),
        interface="# Library\n\n```\nmake_widget(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Widget** — a test term.\n",
        dependency_interfaces={},
        module_names=[],
    )


def test_ac_author_013_prompt_holds_realizes_line(tmp_path):
    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-f]+)-----", prompt)
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

    test_author.author_test(
        _make_bundle(), "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()