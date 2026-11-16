import json
import re
from pathlib import Path

import pytest

import test_author


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"
CRITERION_ID = "AC-FOO-003"
MODEL = "claude-sonnet-5"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _field(value, name):
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _error_text(err):
    if err is None:
        return ""
    if isinstance(err, dict):
        return json.dumps(err, default=str)
    parts = [str(err)]
    for n in ("category", "message", "function", "name", "detail", "details"):
        v = getattr(err, n, None)
        if v is not None:
            parts.append(str(v))
    return " ".join(parts)


def _library_md(*signatures):
    lines = ["# Library", "", "```"]
    lines.extend(signatures)
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def _make_bundle(dependency_interfaces):
    return _Bundle(
        component_id=COMPONENT_ID,
        criterion_id=CRITERION_ID,
        covers="R-FOO-003",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text="**R-FOO-003** — `foo(x)` MUST return `2 * x`.",
        interface=_library_md("foo(x: int) -> int"),
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces=dict(dependency_interfaces),
        module_names=["foo"],
    )


BAR_INTERFACES = {
    "comp-bar": _library_md("do_thing(a: int, b: str, c: dict[str, str]) -> bool"),
}

SCAN_INTERFACES = {
    "comp-alpha": _library_md("scan(component_id: str, repo_root: Path) -> dict"),
    "comp-beta": _library_md("scan(repo_root: Path) -> dict"),
}


def _test_file(*fake_lines):
    lines = ["import foo", "", ""]
    lines.extend(fake_lines)
    lines.extend(
        [
            "",
            "",
            "def test_ac_foo_003():",
            "    assert foo.foo(2) == 4",
            "",
        ]
    )
    return "\n".join(lines)


VALID_PLAIN = _test_file("# no fakes needed")

MALFORMED = "This is <<< not ::: python at all ))) {{ def ( ]] = = =\n"

DO_THING_TWO_ARGS = _test_file(
    "def _fake_do_thing(a, b):",
    "    return True",
    "",
    "",
    "do_thing = _fake_do_thing",
)

DO_THING_THREE_ARGS = _test_file(
    "def _fake_do_thing(a, b, c):",
    "    return True",
    "",
    "",
    "do_thing = _fake_do_thing",
)

SCAN_TWO_ARGS = _test_file(
    "def scan(component_id, repo_root):",
    "    return {}",
)

SCAN_ONE_ARG = _test_file(
    "def scan(repo_root):",
    "    return {}",
)

SCAN_THREE_ARGS = _test_file(
    "def scan(a, b, c):",
    "    return {}",
)


def _make_backend(response_body, log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        text_prompt = prompt if isinstance(prompt, str) else str(prompt)
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", text_prompt)
        if m is None:
            m = re.search(r"\b([0-9a-f]{32})\b", text_prompt)
        nonce = m.group(1) if m else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + response_body
            + "\n-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _call_count(log_path):
    if not Path(log_path).exists():
        return 0
    return len([ln for ln in Path(log_path).read_text().splitlines() if ln.strip()])


def _fresh_repo(base, name, monkeypatch):
    repo_root = base / name
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(repo_root)
    return repo_root


def _files_under(path):
    path = Path(path)
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


def _assert_nothing_written(repo_root):
    cache_files = _files_under(repo_root / ".hotdocs" / "cache")
    assert cache_files == [], f"unexpected cache entries: {cache_files}"
    out_files = _files_under(repo_root / "verification" / COMPONENT_SLUG / "generated-test")
    assert out_files == [], f"unexpected generated-test files: {out_files}"


def _run(bundle, response_body, repo_root, log_path):
    backend = _make_backend(response_body, log_path)
    return test_author.author_test(
        bundle, MODEL, 0, repo_root=repo_root, llm_backend=backend
    )


def _assert_success(result, repo_root, response_body):
    err = _field(result, "model_call_error")
    assert err is None, f"expected success, got model_call_error: {_error_text(err)}"
    file_entry = _field(result, "file")
    assert file_entry is not None
    content = _field(file_entry, "content")
    assert isinstance(content, str)
    assert content.strip() == response_body.strip()
    path = _field(file_entry, "path")
    assert path
    p = Path(path)
    if not p.is_absolute():
        p = repo_root / p
    assert p.is_file(), f"expected the accepted test to be written at {p}"


def _assert_rejected(result, category, repo_root):
    err = _field(result, "model_call_error")
    assert err is not None, "expected a model_call_error"
    assert _field(err, "category") == category, _error_text(err)
    assert _field(result, "file") is None
    assert _field(result, "cache_hit") is not True
    _assert_nothing_written(repo_root)
    return err


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)


# ---------------------------------------------------------------------------
# Scenario 1: syntax check
# ---------------------------------------------------------------------------


def test_malformed_python_is_rejected_and_nothing_written(tmp_path, monkeypatch):
    repo_root = _fresh_repo(tmp_path, "repo_malformed", monkeypatch)
    log_path = tmp_path / "calls_malformed.log"
    bundle = _make_bundle(BAR_INTERFACES)

    result = _run(bundle, MALFORMED, repo_root, log_path)

    assert _call_count(log_path) >= 1, "the mock model was never called"
    _assert_rejected(result, "malformed_code", repo_root)

    # Nothing was cached: a later valid call under the same key is a miss
    # and reaches the model again.
    before = _call_count(log_path)
    follow_up = _run(bundle, VALID_PLAIN, repo_root, log_path)
    assert _call_count(log_path) > before
    assert _field(follow_up, "cache_hit") is False
    _assert_success(follow_up, repo_root, VALID_PLAIN)


# ---------------------------------------------------------------------------
# Scenario 2: fake arity mismatch via alias
# ---------------------------------------------------------------------------


def test_two_arg_fake_aliased_to_do_thing_is_rejected(tmp_path, monkeypatch):
    repo_root = _fresh_repo(tmp_path, "repo_mismatch", monkeypatch)
    log_path = tmp_path / "calls_mismatch.log"
    bundle = _make_bundle(BAR_INTERFACES)

    result = _run(bundle, DO_THING_TWO_ARGS, repo_root, log_path)

    assert _call_count(log_path) >= 1, "the mock model was never called"
    err = _assert_rejected(result, "fake_signature_mismatch", repo_root)
    assert "do_thing" in _error_text(err)

    # Nothing was cached: a later call under the same key reaches the model.
    before = _call_count(log_path)
    follow_up = _run(bundle, DO_THING_THREE_ARGS, repo_root, log_path)
    assert _call_count(log_path) > before
    assert _field(follow_up, "cache_hit") is False
    _assert_success(follow_up, repo_root, DO_THING_THREE_ARGS)


# ---------------------------------------------------------------------------
# Scenario 3: matching arity (bracketed comma is not a separator)
# ---------------------------------------------------------------------------


def test_three_arg_fake_aliased_to_do_thing_succeeds(tmp_path, monkeypatch):
    repo_root = _fresh_repo(tmp_path, "repo_match", monkeypatch)
    log_path = tmp_path / "calls_match.log"
    bundle = _make_bundle(BAR_INTERFACES)

    result = _run(bundle, DO_THING_THREE_ARGS, repo_root, log_path)

    assert _call_count(log_path) >= 1, "the mock model was never called"
    _assert_success(result, repo_root, DO_THING_THREE_ARGS)


# ---------------------------------------------------------------------------
# Scenario 4: a name defined by more than one dependency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_name, body",
    [("two_params", SCAN_TWO_ARGS), ("one_param", SCAN_ONE_ARG)],
)
def test_scan_fake_matching_any_dependency_arity_is_accepted(
    tmp_path, monkeypatch, case_name, body
):
    repo_root = _fresh_repo(tmp_path, "repo_scan_" + case_name, monkeypatch)
    log_path = tmp_path / ("calls_scan_" + case_name + ".log")
    bundle = _make_bundle(SCAN_INTERFACES)

    result = _run(bundle, body, repo_root, log_path)

    assert _call_count(log_path) >= 1, "the mock model was never called"
    _assert_success(result, repo_root, body)


def test_scan_fake_matching_no_dependency_arity_is_rejected(tmp_path, monkeypatch):
    repo_root = _fresh_repo(tmp_path, "repo_scan_three", monkeypatch)
    log_path = tmp_path / "calls_scan_three.log"
    bundle = _make_bundle(SCAN_INTERFACES)

    result = _run(bundle, SCAN_THREE_ARGS, repo_root, log_path)

    assert _call_count(log_path) >= 1, "the mock model was never called"
    err = _assert_rejected(result, "fake_signature_mismatch", repo_root)
    assert "scan" in _error_text(err)