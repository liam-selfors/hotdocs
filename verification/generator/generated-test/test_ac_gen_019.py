import importlib.util
import json
import re
import sys
import uuid
from pathlib import Path

import pytest

import generator


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _tool_root_gen():
    return next(
        p for p in Path(generator.__file__).resolve().parents if p.name == "gen"
    )


def _load_spec_bundle_assembler():
    gen = _tool_root_gen()
    base = gen / "spec-bundle-assembler"
    flat = base / "spec_bundle_assembler.py"
    pkg = base / "spec_bundle_assembler" / "__init__.py"
    path = flat if flat.is_file() else pkg
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("spec_bundle_assembler", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_bundle_assembler"] = module
    spec.loader.exec_module(module)
    return module


class _DuckSpecBundle:
    _FIELDS = (
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._FIELDS:
            return default
        return getattr(self, key)

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)


def _make_cold_bundle(with_dependency):
    unique = uuid.uuid4().hex
    kwargs = dict(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + (unique * 2),
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
            "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )
    if with_dependency:
        kwargs["dependency_interfaces"] = {
            "comp-bar": "# Library\n\n```\nbar(x: int) -> int\n```"
        }
        kwargs["dependency_context"] = {"comp-bar": "Bar adds one to a number."}
        kwargs["dependency_usage"] = {
            "comp-bar": "gen/bar/bar.py\n\ndef bar(x: int) -> int:\n    \"\"\"Add one.\"\"\""
        }
    sba = _load_spec_bundle_assembler()
    cls = getattr(sba, "SpecBundle", None) if sba is not None else None
    if cls is not None:
        try:
            return cls(**kwargs)
        except TypeError:
            pass
    return _DuckSpecBundle(**kwargs)


def _write_component_md(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
        encoding="utf-8",
    )


def _extract_nonce(prompt):
    m = re.search(r"BEGIN FILE\s+([0-9a-f]{32})", prompt)
    if m:
        return m.group(1)
    tokens = re.findall(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])", prompt)
    if tokens:
        return tokens[-1]
    return uuid.uuid4().hex


def _make_backend(log_path):
    def backend(prompt, model, **params):
        records = []
        if log_path.exists():
            records = json.loads(log_path.read_text(encoding="utf-8"))
        records.append({"prompt": prompt, "model": model})
        log_path.write_text(json.dumps(records), encoding="utf-8")
        nonce = _extract_nonce(prompt)
        text = (
            "Here is the candidate.\n"
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    log_dir = tmp_path / "log"
    log_dir.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root, log_dir / "calls.json"


@pytest.mark.parametrize("with_dependency", [False, True])
def test_prompt_instructs_dependency_loads_resolve_from_repo_root(
    isolated_env, with_dependency
):
    repo_root, log_path = isolated_env
    _write_component_md(repo_root)
    bundle = _make_cold_bundle(with_dependency)

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )

    assert _field(result, "refused") is None
    assert log_path.exists(), "mock model was never called"
    records = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(records) >= 1
    prompt = records[0]["prompt"]
    assert isinstance(prompt, str)
    lowered = prompt.lower()

    # Resolve from the repo_root parameter the candidate's function received.
    assert "repo_root" in prompt
    # Forbidden mechanisms each named explicitly.
    assert "sys.modules" in prompt
    assert "__file__" in prompt
    assert "import" in lowered
    # The gen/<dep-slug>/ module path.
    assert "gen/" in prompt
    # Fallback to the tool root when absent from repo_root.
    assert any(
        phrase in lowered
        for phrase in (
            "tool root",
            "tool's root",
            "tool's own",
            "tool’s own",
            "tool’s root",
            "nearest gen",
            "nearest `gen`",
        )
    ), "prompt never mentions falling back to the tool root"
    assert any(
        phrase in lowered for phrase in ("absent", "missing", "not present", "does not exist", "doesn't exist")
    ), "prompt never states the tool-root fallback applies only when absent"


def test_generate_completes_with_repo_root_lacking_gen(isolated_env):
    repo_root, log_path = isolated_env
    _write_component_md(repo_root)
    assert not (repo_root / "gen").exists()
    bundle = _make_cold_bundle(False)

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )

    assert result is not None
    assert _field(result, "model_call_error") is None
    assert _field(result, "refused") is None
    files = _field(result, "files")
    assert files, "expected a non-empty files mapping"
    assert "foo.py" in files
    assert "return 2 * x" in files["foo.py"]
    assert _field(result, "component_id") == "comp-foo"
    assert log_path.exists(), "mock model was never called"