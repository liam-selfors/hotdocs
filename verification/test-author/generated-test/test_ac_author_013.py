# hotdocs-criterion: sha256:3818c6bb5b4f6f9b1cbad0319cf82577980408db08e758de309185eae04c92fe
import re

import test_author


EXPECTED_LINE = (
    "- Only a criterion that needs `realizes`-driven behavior has the fixture "
    "supply a resolvable `P-<id>`."
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
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs[name])

    def __getitem__(self, key):
        if key in self._FIELDS:
            return getattr(self, key)
        raise KeyError(key)

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
            "Given a widget name \"w\"\n"
            "When make_widget(\"w\") is called\n"
            "Then it returns a widget named \"w\""
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** — `make_widget(name)` MUST return a widget "
            "whose name is `name`."
        ),
        interface="# Library\n\n```\nmake_widget(name: str) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** — a test term.\n",
        dependency_interfaces={},
    )


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

_TEST_BODY = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make_widget():\n"
    "    assert widget_maker is not None\n"
)


def test_prompt_contains_realizes_fixture_line(tmp_path):
    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = _NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + _TEST_BODY
            + "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _make_bundle()
    test_author.author_test(
        bundle, "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()