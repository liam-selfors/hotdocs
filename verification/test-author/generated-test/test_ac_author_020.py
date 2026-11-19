# hotdocs-criterion: sha256:fb71e6a9110f9a42a81692de9807bfe83ba5b910e361a3d8e60be2ceb088ca30
import dataclasses
import re

import pytest

import test_author


MODEL = "claude-sonnet-5"
COMPONENT_ID = "comp-foo"
SLUG = "foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class Bundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    module_names: list = dataclasses.field(default_factory=list)

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

    def keys(self):
        return list(self._names())

    def items(self):
        return [(k, getattr(self, k)) for k in self._names()]

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


def make_bundle(dependency_interfaces):
    return Bundle(
        component_id=COMPONENT_ID,
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces=dependency_interfaces,
        module_names=["foo"],
    )


def lib_doc(signature):
    return "# Library\n\n```\n" + signature + "\n```\n"


def make_backend(content, log):
    def backend(prompt, model, **params):
        log.append(prompt)
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        assert m is not None, "prompt does not carry a BEGIN FILE nonce"
        nonce = m.group(1)
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


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    return root


def files_under(path):
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


def assert_nothing_written(repo_root):
    out_dir = repo_root / "verification" / SLUG / "generated-test"
    assert files_under(out_dir) == [], "a test file was written despite a rejected response"
    cache_dir = repo_root / ".hotdocs" / "cache"
    assert files_under(cache_dir) == [], "a cache entry was written despite a rejected response"


def run(repo_root, bundle, content, seed=0):
    log = []
    result = test_author.author_test(
        bundle, MODEL, seed, repo_root=repo_root, llm_backend=make_backend(content, log)
    )
    assert log, "mock backend was never called"
    return result


def error_text(err):
    if isinstance(err, dict):
        return " ".join(str(v) for v in err.values())
    parts = []
    for name in ("category", "message"):
        if hasattr(err, name):
            parts.append(str(getattr(err, name)))
    return " ".join(parts) + " " + str(err)


def assert_rejected(result, category, repo_root):
    err = field(result, "model_call_error")
    assert err is not None, "expected a model_call_error"
    assert field(err, "category") == category
    assert field(result, "file") is None
    assert_nothing_written(repo_root)
    return err


def assert_accepted(result):
    assert field(result, "model_call_error") is None
    assert field(result, "file") is not None


# --- Scenario 1: not Python at all -------------------------------------------

def test_malformed_code_is_rejected(repo_root):
    bundle = make_bundle({"comp-bar": lib_doc("do_thing(a: int, b: str, c: dict[str, str]) -> bool")})
    content = "this is ) not (( python at all :: def\n    }}} ???"
    result = run(repo_root, bundle, content)
    assert_rejected(result, "malformed_code", repo_root)


# --- Scenario 2/3: monkeypatched fake arity -----------------------------------

def monkeypatch_body(params):
    lines = [
        "import foo",
        "",
        "",
        "def fake(" + ", ".join(params) + "):",
        "    return True",
        "",
        "",
        "def test_uses_fake(monkeypatch):",
        "    monkeypatch.setattr(foo, " + repr("do_thing") + ", fake)",
        "    assert True",
        "",
    ]
    return "\n".join(lines)


def test_two_arg_monkeypatched_fake_is_signature_mismatch(repo_root):
    bundle = make_bundle({"comp-bar": lib_doc("do_thing(a: int, b: str, c: dict[str, str]) -> bool")})
    result = run(repo_root, bundle, monkeypatch_body(["a", "b"]))
    err = assert_rejected(result, "fake_signature_mismatch", repo_root)
    assert "do_thing" in error_text(err)


def test_three_arg_monkeypatched_fake_is_accepted(repo_root):
    bundle = make_bundle({"comp-bar": lib_doc("do_thing(a: int, b: str, c: dict[str, str]) -> bool")})
    result = run(repo_root, bundle, monkeypatch_body(["a", "b", "c"]))
    assert_accepted(result)


# --- Scenario 4: name defined by several dependencies -------------------------

def scan_deps():
    return {
        "comp-alpha": lib_doc("scan(component_id: str, repo_root: Path) -> dict"),
        "comp-beta": lib_doc("scan(repo_root: Path) -> dict"),
    }


def fake_module_body(params):
    src = "def scan(" + ", ".join(params) + "):\n    return {}\n"
    lines = [
        "SRC = " + repr(src),
        "",
        "",
        "def test_writes_fake(tmp_path):",
        "    path = tmp_path / " + repr("gen") + " / " + repr("alpha") + " / " + repr("alpha.py"),
        "    path.parent.mkdir(parents=True)",
        "    path.write_text(SRC)",
        "    assert path.read_text() == SRC",
        "",
    ]
    return "\n".join(lines)


@pytest.mark.parametrize("params", [["component_id", "repo_root"], ["repo_root"]])
def test_fake_module_scan_matching_any_dependency_arity_is_accepted(repo_root, params):
    result = run(repo_root, make_bundle(scan_deps()), fake_module_body(params))
    assert_accepted(result)


def test_fake_module_scan_matching_no_dependency_arity_is_rejected(repo_root):
    result = run(
        repo_root, make_bundle(scan_deps()), fake_module_body(["component_id", "repo_root", "extra"])
    )
    err = assert_rejected(result, "fake_signature_mismatch", repo_root)
    assert "scan" in error_text(err)