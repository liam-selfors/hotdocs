# hotdocs-criterion: sha256:6b331b90b7ec95d4b0f51c7299165b0a9bcfa8e56c04eec8ef9537cf0b76fa97
import re
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A SpecBundle-shaped object readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id="comp-foo-bar",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Foo Bar\n\n## Purpose\n\nFoo bar doubles a number.\n\n# R-FOO-BAR-001\n\n**R-FOO-BAR-001** — `foo_bar(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo_bar(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def write_component(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo-bar"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo-bar\n"
        "title: Foo Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo bar doubles a number.\n",
        encoding="utf-8",
    )


def find_nonce(prompt):
    m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})\b", prompt)
    if m:
        return m.group(1)
    candidates = re.findall(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])", prompt)
    assert candidates, "no nonce found in prompt"
    return candidates[0]


def test_ac_gen_021_redundant_component_prefix_is_stripped(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_component(repo_root)

    log_path = tmp_path / "backend_calls.log"

    returned = {
        "foo-bar/foo_bar.py": "def foo_bar(x):\n    return 2 * x\n",
        "gen/foo-bar/helpers/__init__.py": "HELPER = 1\n",
        "foo_bar_extra.py": "EXTRA = 2\n",
    }

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = find_nonce(prompt)
        parts = ["Here are the files.\n"]
        for path, content in returned.items():
            parts.append("-----BEGIN FILE " + nonce + ": " + path + "-----\n")
            parts.append(content)
            if not content.endswith("\n"):
                parts.append("\n")
            parts.append("-----END FILE " + nonce + "-----\n")
        return {
            "text": "".join(parts),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        make_bundle(), "mock-model", repo_root=repo_root, llm_backend=backend
    )

    assert log_path.exists(), "mock model was never called"
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None

    out = repo_root / "gen" / "foo-bar"
    assert (out / "foo_bar.py").is_file()
    assert (out / "helpers" / "__init__.py").is_file()
    assert (out / "foo_bar_extra.py").is_file()

    assert (out / "foo_bar.py").read_text(encoding="utf-8").strip() == "def foo_bar(x):\n    return 2 * x"
    assert (out / "helpers" / "__init__.py").read_text(encoding="utf-8").strip() == "HELPER = 1"
    assert (out / "foo_bar_extra.py").read_text(encoding="utf-8").strip() == "EXTRA = 2"

    assert not (out / "foo-bar").exists(), "nothing may be written under gen/foo-bar/foo-bar/"
    assert not (out / "gen").exists(), "nothing may be written under gen/foo-bar/gen/"