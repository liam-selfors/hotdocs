import json
import re
from pathlib import Path

import pytest

import test_author


TEST_FILE_BODY = "def test_placeholder():\n    assert 2 * 2 == 4\n"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _extract_nonce(prompt):
    m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
    if m:
        return m.group(1)
    m = re.search(r"BEGIN FILE\s+([0-9a-f]{32})", prompt)
    if m:
        return m.group(1)
    candidates = re.findall(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])", prompt)
    if candidates:
        return candidates[0]
    return None


def _make_backend(log_path):
    def backend(prompt, model, **params):
        nonce = _extract_nonce(prompt)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model, "nonce_found": nonce is not None}) + "\n")
        text = (
            f"-----BEGIN FILE {nonce}-----\n"
            f"{TEST_FILE_BODY}"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


class _ObjectBundle:
    """A plain, non-dict CriterionBundle-shaped object with NO dependency_interfaces."""

    def __init__(self):
        self.component_id = "comp-foo"
        self.criterion_id = "AC-FOO-001"
        self.covers = "R-FOO-001"
        self.criterion_text = "Given x = 2\nWhen foo(x) is called\nThen it returns 4\n"
        self.requirement_text = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        self.interface = "# Library\n\n```\nfoo(x: int) -> int\n```\n"
        self.glossary = "# Glossary\n\n- **Foo** — a test term.\n"


def _dict_bundle():
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "Given x = 2\nWhen foo(x) is called\nThen it returns 4\n",
        "requirement_text": "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```\n",
        "glossary": "# Glossary\n\n- **Foo** — a test term.\n",
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "backend_calls.log"
    return repo_root, log_path


def _assert_completed(result, log_path):
    assert result is not None
    assert _get(result, "model_call_error") is None
    file_ = _get(result, "file")
    assert file_ is not None
    content = _get(file_, "content")
    assert isinstance(content, str) and content.strip() != ""
    assert "def test_placeholder" in content
    assert _get(result, "component_id") == "comp-foo"
    assert _get(result, "criterion_id") == "AC-FOO-001"
    # The mock backend was actually reached (unless served from cache, which a
    # fresh repo_root rules out).
    if not _get(result, "cache_hit"):
        assert log_path.is_file()
        records = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(records) >= 1


def test_object_bundle_without_dependency_interfaces_does_not_raise(env):
    repo_root, log_path = env
    bundle = _ObjectBundle()
    assert not hasattr(bundle, "dependency_interfaces")
    assert not isinstance(bundle, dict)

    try:
        result = test_author.author_test(
            bundle,
            "claude-sonnet-5",
            0,
            repo_root=repo_root,
            llm_backend=_make_backend(log_path),
        )
    except AttributeError as exc:  # pragma: no cover - failure path
        pytest.fail(f"author_test raised AttributeError on a bundle missing dependency_interfaces: {exc!r}")

    _assert_completed(result, log_path)


def test_dict_bundle_without_dependency_interfaces_key_does_not_raise(env):
    repo_root, log_path = env
    bundle = _dict_bundle()
    assert "dependency_interfaces" not in bundle

    try:
        result = test_author.author_test(
            bundle,
            "claude-sonnet-5",
            0,
            repo_root=repo_root,
            llm_backend=_make_backend(log_path),
        )
    except KeyError as exc:  # pragma: no cover - failure path
        pytest.fail(f"author_test raised KeyError on a bundle missing dependency_interfaces: {exc!r}")

    _assert_completed(result, log_path)