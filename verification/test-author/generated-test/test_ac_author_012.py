# hotdocs-criterion: sha256:fb1c28b36326822d9c2bc84c710f7fe9e01d6eb87cdf2b3e44697b29c4d2fcae
import dataclasses
import re

import test_author


LINE_RATIFIED = (
    "- A document with `status: ratified` also sets the placeholder "
    "`last_ratified_commit: 0000000`."
)
LINE_NO_YAML = (
    "- A test MUST NEVER `import yaml` or any other third-party package "
    "not already installed: it writes and parses frontmatter as plain text."
)


@dataclasses.dataclass
class FakeCriterionBundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        if key in self._names():
            return getattr(self, key)
        return default

    def __contains__(self, key):
        return key in self._names()

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def keys(self):
        return list(self._names())

    def values(self):
        return [getattr(self, n) for n in self._names()]

    def items(self):
        return [(n, getattr(self, n)) for n in self._names()]


def make_bundle():
    return FakeCriterionBundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=(
            "Given a width of 3\n"
            "When make_widget(3) is called\n"
            "Then it returns a widget of width 3"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** \u2014 `make_widget(w)` MUST return a widget of width `w`."
        ),
        interface="# Library\n\n```\nmake_widget(w: int) -> dict\n```",
        glossary="# Glossary\n\n- **Widget** \u2014 a test term.",
        dependency_interfaces={},
    )


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def make_mock(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        m = NONCE_RE.search(prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n"
            "\n"
            "def test_widget():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_prompt_holds_block_r_author_012_lines(tmp_path):
    prompts = []
    backend = make_mock(prompts)
    bundle = make_bundle()

    test_author.author_test(bundle, "mock", repo_root=tmp_path, llm_backend=backend)

    assert len(prompts) >= 1, "the mock model was never called"
    lines = prompts[0].splitlines()
    assert LINE_RATIFIED in lines
    assert LINE_NO_YAML in lines