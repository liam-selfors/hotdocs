import os
import re
from pathlib import Path

import pytest

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle(dependency_interfaces):
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-003",
        covers="R-FOO-003",
        criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        requirement_text="**R-FOO-003** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces=dependency_interfaces,
        module_names=["foo"],
    )


def write_fake_cache_manager(repo_root, log_path):
    src = (
        "import dataclasses\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "    def __hash__(self):\n"
        "        return 0\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str = ''\n"
        "    gate_inputs_hash: str = ''\n"
        "    gate_version: str = ''\n"
        "    model_pin: str = ''\n"
        "    def __getitem__(self, k):\n"
        "        return getattr(self, k)\n"
        "    def get(self, k, d=None):\n"
        "        return getattr(self, k, d)\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str = ''\n"
        "    payload: dict = None\n"
        "    stored_at: str = ''\n"
        "    def __getitem__(self, k):\n"
        "        return getattr(self, k)\n"
        "    def get(self, k, d=None):\n"
        "        return getattr(self, k, d)\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get')\n"
        "    return Miss()\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put')\n"
        "    return None\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 0}\n"
    )
    d = Path(repo_root) / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(src)


def make_backend(content, prompt_log):
    def backend(prompt, model, **params):
        prompt_log.append(prompt)
        found = NONCE_RE.findall(prompt)
        assert found, "prompt holds no BEGIN FILE nonce"
        n = found[0]
        text = "-----BEGIN FILE " + n + "-----\n" + content + "\n-----END FILE " + n + "-----"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    write_fake_cache_manager(repo_root, log_path)
    monkeypatch.chdir(repo_root)
    return repo_root, log_path


def run(repo_root, bundle, content, seed=0):
    prompts = []
    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        seed,
        repo_root=repo_root,
        llm_backend=make_backend(content, prompts),
    )
    assert prompts, "the mock backend was never called"
    return result


def put_count(log_path):
    if not log_path.exists():
        return 0
    return sum(1 for line in log_path.read_text().splitlines() if line.strip() == "put")


def generated_dir_files(repo_root):
    d = Path(repo_root) / "verification" / "foo" / "generated-test"
    if not d.exists():
        return []
    return [p for p in d.rglob("*") if p.is_file()]


def assert_rejected(result, category, repo_root, log_path, name=None):
    err = field(result, "model_call_error")
    assert err is not None, "expected a model_call_error"
    assert field(err, "category") == category
    if name is not None:
        try:
            message = field(err, "message")
        except (KeyError, AttributeError):
            message = None
        assert name in str(message) or name in repr(err)
    assert field(result, "file") is None
    assert put_count(log_path) == 0, "a rejected response was cached"
    assert generated_dir_files(repo_root) == [], "a rejected response was written"


def assert_accepted(result):
    assert field(result, "model_call_error") is None
    assert field(result, "file") is not None


DO_THING_IFACE = {
    "comp-bar": "# Library\n\n```\ndo_thing(a: int, b: str, c: dict[str, str]) -> bool\n```\n",
}

SCAN_IFACES = {
    "comp-bar": "# Library\n\n```\nscan(component_id: str, repo_root: Path) -> dict\n```\n",
    "comp-baz": "# Library\n\n```\nscan(repo_root: Path) -> dict\n```\n",
}


def test_not_python_is_malformed_code(env):
    repo_root, log_path = env
    content = "this is (not python at all\n  ::: }{ def def\n"
    result = run(repo_root, make_bundle(DO_THING_IFACE), content, seed=1)
    assert_rejected(result, "malformed_code", repo_root, log_path)


def test_two_arg_fake_alias_is_signature_mismatch(env):
    repo_root, log_path = env
    content = (
        "def _fake_do_thing(a, b):\n"
        "    return True\n"
        "\n"
        "do_thing = _fake_do_thing\n"
        "\n"
        "def test_something():\n"
        "    assert do_thing(1, 'x') is True\n"
    )
    result = run(repo_root, make_bundle(DO_THING_IFACE), content, seed=2)
    assert_rejected(result, "fake_signature_mismatch", repo_root, log_path, name="do_thing")


def test_three_arg_fake_alias_is_accepted(env):
    repo_root, log_path = env
    content = (
        "def _fake_do_thing(a, b, c):\n"
        "    return True\n"
        "\n"
        "do_thing = _fake_do_thing\n"
        "\n"
        "def test_something():\n"
        "    assert do_thing(1, 'x', {'k': 'v'}) is True\n"
    )
    result = run(repo_root, make_bundle(DO_THING_IFACE), content, seed=3)
    assert_accepted(result)


@pytest.mark.parametrize(
    "params, seed",
    [("component_id, repo_root", 4), ("repo_root", 5)],
)
def test_scan_matching_either_dependency_is_accepted(env, params, seed):
    repo_root, log_path = env
    content = (
        "def scan(" + params + "):\n"
        "    return {}\n"
        "\n"
        "def test_scan():\n"
        "    assert scan is not None\n"
    )
    result = run(repo_root, make_bundle(SCAN_IFACES), content, seed=seed)
    assert_accepted(result)


def test_scan_with_three_params_is_rejected(env):
    repo_root, log_path = env
    content = (
        "def scan(component_id, repo_root, extra):\n"
        "    return {}\n"
        "\n"
        "def test_scan():\n"
        "    assert scan is not None\n"
    )
    result = run(repo_root, make_bundle(SCAN_IFACES), content, seed=6)
    assert_rejected(result, "fake_signature_mismatch", repo_root, log_path, name="scan")