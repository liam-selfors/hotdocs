# hotdocs-criterion: sha256:1b8105e8c965f11d90e8392e4abffd42ba55b854ced07c0b1e465286d0455637
import test_author


GLOSSARY = "# Glossary\n\n- **Foo** — a test term."

INTERFACE = "# Library\n\n```\nfoo(x: int) -> int\n```"

CRITERION_TEXT = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

REQUIREMENT_TEXT = "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."


class Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=CRITERION_TEXT,
        requirement_text=REQUIREMENT_TEXT,
        interface=INTERFACE,
        glossary=GLOSSARY,
        dependency_interfaces={},
        module_names=["foo"],
    )


def test_model_network_error_is_reported_as_model_call_error(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "backend_calls.log"

    def failing_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        # The documented ModelResponse shape for a failed (network) call.
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {
                "category": "network",
                "message": "connection failed",
            },
        }

    result = test_author.author_test(
        make_bundle(),
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=failing_backend,
    )

    # The mock model was actually consulted (fresh repo_root: no cache hit).
    assert log_path.is_file()
    assert len(log_path.read_text(encoding="utf-8").splitlines()) >= 1

    assert field(result, "model_call_error") is not None
    assert field(result, "file") is None
    assert field(result, "cache_hit") is False