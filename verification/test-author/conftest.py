import re
import shutil
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "test-author"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "cache-manager"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "llm-endpoint"))
sys.path.insert(0, str(REPO_ROOT / "gen" / "spec-bundle-assembler"))
import test_author  # noqa: E402
import cache_manager  # noqa: E402
import spec_bundle_assembler  # noqa: E402


def fake_bundle_dict(**overrides) -> dict:
    base = {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-003",
        "covers": "R-FOO-003",
        "criterion_text": "FAKE CRITERION TEXT",
        "requirement_text": "FAKE REQUIREMENT TEXT",
        "interface": "FAKE INTERFACE TEXT",
        "glossary": "FAKE GLOSSARY TEXT",
        "dependency_interfaces": {},
    }
    base.update(overrides)
    return base


def fake_bundle(**overrides):
    """The installed test_author.author_test accesses bundle fields via
    plain attribute access (bundle.component_id, ...) against a bare `Any`
    -typed parameter (D94 dropped test_author's own redundant
    CriterionBundle class in favor of duck typing, consistent with the
    corpus's general plain-value cross-component convention) -- any
    object exposing the same attributes works, so a SimpleNamespace is
    enough here."""
    return types.SimpleNamespace(**fake_bundle_dict(**overrides))


def file_block(content: str, wrapper: str = "{marked}"):
    """A mock backend reply wrapping `content` in the real nonce-delimited
    BEGIN/END markers the candidate's prompt asks for (R-AUTHOR-009,
    D94) -- the nonce is read back out of the prompt actually sent,
    never assumed, since it is freshly random per call. `wrapper` lets a
    test place extra narration/fencing around the marked block while
    still producing a response the real extractor must handle."""
    def _build(prompt, model, **params):
        m = re.search(r"-----BEGIN FILE (\S+)-----", prompt)
        nonce = m.group(1) if m else "MISSING-NONCE"
        marked = f"-----BEGIN FILE {nonce}-----\n{content}\n-----END FILE {nonce}-----"
        return {"text": wrapper.format(marked=marked), "model_call_error": None}
    return _build


class MockBackend:
    """Deliberately strict (D110): the real AnthropicBackend forwards every
    keyword argument verbatim into a CLI flag (R-ENDPOINT-001) and fails if
    the backend CLI doesn't recognize it -- a silently permissive mock here
    is exactly what let the seed-forwarding bug (D108) through every
    AC-AUTHOR-* criterion invisibly. Any unexpected kwarg is now a hard
    error, the same as the real backend's own failure mode, so a future
    instance of this bug class is caught here instead of only surfacing in
    a real bootstrap."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []

    def __call__(self, prompt, model, **params):
        if params:
            raise TypeError(
                f"MockBackend received unexpected keyword argument(s) {sorted(params)} -- "
                "the real backend forwards every kwarg verbatim into a CLI flag and fails "
                "if it isn't recognized (R-ENDPOINT-001); author_test must pass only "
                "prompt/model/backend to llm_endpoint.complete()."
            )
        self.calls.append((prompt, model, params))
        result = self._results.pop(0)
        return result(prompt, model) if callable(result) else result


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    """test_author.author_test loads cache-manager/llm-endpoint dynamically
    from <repo_root>/gen/ per call, not via a static sys.path import -- a
    real copy of each must exist under tmp_path for any test to reach past
    the first dependency load."""
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    shutil.copytree(REPO_ROOT / "gen" / "cache-manager", tmp_path / "gen" / "cache-manager")
    shutil.copytree(REPO_ROOT / "gen" / "llm-endpoint", tmp_path / "gen" / "llm-endpoint")
    return tmp_path
