# hotdocs-criterion: sha256:b047ca0bf3500ca9998eeef0fe2f562d9350a675d9e406cffea7bd79d7fc9c90
import dataclasses
import re
from dataclasses import dataclass, field as dc_field

import test_author


BLOCK_LINE = "a fake MUST return every field, never a bare list, string or number in its place"
DEP_ID = "comp-zebra-quux"
DEP_IFACE = "zq_lookup(x: int, y: str) -> ZqResult"

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class Bundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    module_names: list = dc_field(default_factory=list)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __contains__(self, key):
        return key in self.keys()

    def __iter__(self):
        return iter(self.keys())

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]

    def values(self):
        return [getattr(self, k) for k in self.keys()]


def make_bundle(dependency_interfaces):
    return Bundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=(
            "Given a widget spec\n"
            "When make_widget(spec) is called\n"
            "Then it returns a widget"
        ),
        requirement_text=(
            "# R-WIDGET-MAKER-001\n\n"
            "**R-WIDGET-MAKER-001** — `make_widget(spec)` MUST return a widget."
        ),
        interface="# Library\n\n```\nmake_widget(spec: dict) -> dict\n```",
        glossary="# Glossary\n\n- **Widget** — a test term.",
        dependency_interfaces=dict(dependency_interfaces),
        module_names=["widget_maker"],
    )


def make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        m = NONCE_RE.search(prompt)
        nonce = m.group(1) if m else ""
        content = "import widget_maker\n\n\ndef test_placeholder():\n    assert True"
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + content
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_prompt_includes_dependency_interface_and_fake_rule(tmp_path):
    repo_root = tmp_path / "repo_with_dep"
    repo_root.mkdir()
    prompts = []
    bundle = make_bundle({DEP_ID: DEP_IFACE})

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_backend(prompts)
    )

    assert len(prompts) >= 1, "mock model was never called"
    first = prompts[0]
    assert DEP_ID in first
    assert DEP_IFACE in first
    assert BLOCK_LINE in first


def test_empty_dependency_interfaces_adds_no_entry(tmp_path):
    repo_root = tmp_path / "repo_no_dep"
    repo_root.mkdir()
    prompts = []
    bundle = make_bundle({})

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_backend(prompts)
    )

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1, "mock model was never called"
    first = prompts[0]
    assert DEP_ID not in first