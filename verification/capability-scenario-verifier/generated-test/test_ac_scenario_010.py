import json
import shutil
import textwrap
from pathlib import Path

import capability_scenario_verifier


GHERKIN = (
    "Given a fixture-value is 1\n"
    "When the assembled system runs\n"
    "Then the outcome equals 1\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _SentinelBackend:
    def __call__(self, prompt, model, **params):
        return {
            "text": "unused",
            "model": model,
            "backend": "sentinel",
            "model_call_error": None,
        }

    def __repr__(self):
        return "SENTINEL_BACKEND_OBJECT"


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root: Path, slug: str, iface_text: str):
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        textwrap.dedent(
            f"""\
            ---
            id: comp-{slug}
            title: {slug.capitalize()} component
            status: draft
            owners: [tester]
            realizes: [P-X]
            sealed: false
            ---

            # comp-{slug}

            A synthetic component.
            """
        ),
    )
    _write(
        repo_root / "specs" / "components" / slug / "interface" / "library.md",
        iface_text + "\n",
    )
    _write(
        repo_root / "gen" / slug / f"{slug}.py",
        "def run():\n    return 1\n",
    )


def _build_repo(repo_root: Path, log_path: Path):
    _component(repo_root, "foo", "FOO_IFACE")
    _component(repo_root, "bar", "BAR_IFACE")
    _write(repo_root / "specs" / "glossary.md", "GLOSS")

    cap_text = (
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# P-X\n"
        "\n"
        "CAPABILITY_X_PROSE the assembled system does X.\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + GHERKIN
        + "```\n"
    )
    _write(repo_root / "specs" / "product" / "x.md", cap_text)

    fake_author = textwrap.dedent(
        f"""\
        import json

        LOG_PATH = {str(log_path)!r}


        def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
            record = {{
                "bundle": bundle,
                "model": model,
                "seed": seed,
                "repo_root": str(repo_root),
                "llm_backend_id": id(llm_backend),
                "llm_backend_repr": repr(llm_backend),
            }}
            with open(LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\\n")
            return {{
                "component_id": bundle.get("component_id") if isinstance(bundle, dict) else None,
                "criterion_id": bundle.get("criterion_id") if isinstance(bundle, dict) else None,
                "model": model,
                "seed": seed,
                "prompt_version": "v1",
                "cache_hit": False,
                "file": {{
                    "path": "verification/capabilities/P-X/generated-test/test_cs_x_001.py",
                    "content": "def test_x():\\n    assert True\\n",
                }},
                "model_call_error": None,
            }}
        """
    )
    _write(repo_root / "gen" / "test-author" / "test_author.py", fake_author)

    fake_endpoint = textwrap.dedent(
        """\
        def complete(prompt, model, *, backend=None, **params):
            return {
                "text": "pass",
                "model": model,
                "backend": "fake",
                "model_call_error": None,
            }
        """
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", fake_endpoint)

    tool_root = _tool_root()
    if tool_root is not None:
        src = tool_root / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

    return cap_text


def test_run_capability_gates_builds_author_test_bundle(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "author_test_calls.jsonl"
    cap_text = _build_repo(repo_root, log_path)

    sentinel = _SentinelBackend()

    capability_scenario_verifier.run_capability_gates(
        "P-X", repo_root, "m", seed=3, llm_backend=sentinel
    )

    assert log_path.exists(), "author_test was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1, f"author_test called {len(lines)} times, expected once"
    call = json.loads(lines[0])

    assert call["model"] == "m"
    assert call["seed"] == 3
    assert Path(call["repo_root"]).resolve() == Path(repo_root).resolve()
    assert call["llm_backend_id"] == id(sentinel)
    assert call["llm_backend_repr"] == "SENTINEL_BACKEND_OBJECT"

    bundle = call["bundle"]
    assert isinstance(bundle, dict)
    assert bundle["component_id"] == "capabilities/P-X"
    assert bundle["criterion_id"] == "CS-X-001"
    assert bundle["covers"] == "P-X"
    assert bundle["criterion_text"].strip() == GHERKIN.strip()
    assert cap_text.strip() in bundle["requirement_text"]
    assert bundle["glossary"] == "GLOSS"
    assert bundle["dependency_interfaces"] == {}
    assert bundle["module_names"] == ["bar", "foo"]

    interface = bundle["interface"]
    i_bar_head = interface.find("## comp-bar")
    i_bar = interface.find("BAR_IFACE")
    i_foo_head = interface.find("## comp-foo")
    i_foo = interface.find("FOO_IFACE")
    assert i_bar_head != -1, interface
    assert i_bar != -1, interface
    assert i_foo_head != -1, interface
    assert i_foo != -1, interface
    assert i_bar_head < i_bar < i_foo_head < i_foo, interface