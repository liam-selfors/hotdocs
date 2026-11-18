# hotdocs-criterion: sha256:299e5ce5aaf366b4fde5f4a9b8fd059fb9b5826647d34a63b64336a1b828c791
import re
import uuid

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        if self.dependency_interfaces is None:
            self.dependency_interfaces = {}
        if self.module_names is None:
            self.module_names = []

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


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def test_ac_author_001_prompt_contains_criterion_requirement_interface_glossary(tmp_path):
    marker = uuid.uuid4().hex

    criterion_text = (
        "Given x = 2 and marker crit-" + marker + "\n"
        "When widget_double(x) is called\n"
        "Then it returns 4"
    )
    requirement_text = (
        "# R-WIDGET-MAKER-001\n\n"
        "**R-WIDGET-MAKER-001** — `widget_double(x)` MUST return `2 * x` (req-"
        + marker
        + ")."
    )
    interface_text = (
        "# Library\n\n"
        "```\n"
        "widget_double(x: int) -> int\n"
        "```\n\n"
        "iface-" + marker
    )
    glossary_text = "# Glossary\n\n- **Widget** — a test term, gloss-" + marker + "."

    bundle = Bundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=criterion_text,
        requirement_text=requirement_text,
        interface=interface_text,
        glossary=glossary_text,
        dependency_interfaces={},
        module_names=["widget_maker"],
    )

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        m = NONCE_RE.search(prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "import widget_maker\n\n\n"
            "def test_x():\n"
            "    assert widget_maker.widget_double(2) == 4\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle,
        "mock-model-" + marker,
        0,
        repo_root=tmp_path,
        llm_backend=mock_backend,
    )

    assert result is not None
    assert field(result, "model_call_error") is None
    assert recorded, "the mock model was never called"

    def holds_all(prompt):
        return (
            criterion_text in prompt
            and requirement_text in prompt
            and interface_text in prompt
            and glossary_text in prompt
        )

    assert any(holds_all(p) for p in recorded), (
        "no recorded model input contained the criterion text, the covered "
        "requirement's text, the interface and the glossary"
    )

    first = recorded[0]
    assert criterion_text in first
    assert requirement_text in first
    assert interface_text in first
    assert glossary_text in first