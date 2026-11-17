import re

import test_author


DEP_ID = "comp-zebra-quux"
DEP_INTERFACE = "zq_lookup(x: int, y: str) -> ZqResult"
RULE_TEXT = "a fake MUST return every field, never a bare list, string or number in its place"

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

REPLY_BODY = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker is not None\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle(dependency_interfaces):
    return _Bundle(
        component_id="comp-widget-maker",
        criterion_id="AC-WIDGET-MAKER-001",
        covers="R-WIDGET-MAKER-001",
        criterion_text=(
            "Given a widget size of 2\n"
            "When make_widget(2) is called\n"
            "Then it returns a widget of size 2"
        ),
        requirement_text=(
            "**R-WIDGET-MAKER-001** - `make_widget(n)` MUST return a widget of size `n`."
        ),
        interface="# Library\n\n```\nmake_widget(n: int) -> dict\n```\n",
        glossary="# Glossary\n\n- **Widget** - a test term.\n",
        dependency_interfaces=dict(dependency_interfaces),
        module_names=["widget_maker"],
    )


class RecordingMock:
    def __init__(self):
        self.prompts = []

    def __call__(self, *args, **kwargs):
        prompt = args[0] if args else kwargs.get("prompt")
        if len(args) > 1:
            model = args[1]
        else:
            model = kwargs.get("model", "mock")
        self.prompts.append(prompt)
        match = NONCE_RE.search(prompt or "")
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + REPLY_BODY
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }


def test_dependency_interfaces_included_in_prompt(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    mock = RecordingMock()
    bundle = make_bundle({DEP_ID: DEP_INTERFACE})

    test_author.author_test(bundle, "mock", repo_root=repo_root, llm_backend=mock)

    assert len(mock.prompts) >= 1
    first = mock.prompts[0]
    assert DEP_ID in first
    assert DEP_INTERFACE in first
    assert RULE_TEXT in first


def test_empty_dependency_interfaces_adds_no_entry(tmp_path):
    repo_root = tmp_path / "repo-empty"
    repo_root.mkdir()
    mock = RecordingMock()
    bundle = make_bundle({})

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock
    )

    assert field(result, "model_call_error") is None
    assert len(mock.prompts) >= 1
    first = mock.prompts[0]
    assert DEP_ID not in first