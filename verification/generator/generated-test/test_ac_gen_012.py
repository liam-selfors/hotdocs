# hotdocs-criterion: sha256:6ed9ce064d8b05328d951fc7f51208fd6485fbb1f4cc068567f78dd06a04154d
"""AC-GEN-012 (covers R-GEN-011): a hanging model call is not retried.

Given a mock model configured to hang (never respond) and the SDK's own
default timeout, when generate is called, then the call eventually
completes with model_call_error set (not an unbounded hang), and the mock
model records exactly one call attempt: no internal retry occurred.

The mock backend stands in for a provider that never answers. The SDK's
default timeout (llm-endpoint's DEFAULT_TIMEOUT_SECONDS) is far too long
to wait out in a unit test, so the mock models the hang as a short block
followed by what the SDK reports once its own timeout fires: a
ModelResponse whose model_call_error has category "timeout". What this
test checks is generator's handling of that outcome: it surfaces the
error once and makes no second attempt.
"""

import threading
import time
import uuid
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
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
    "Foo doubles a number.\n"
)


def _write_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text("# Glossary\n\n- **Foo** — a test term.\n")
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n"
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n")


def _bundle():
    return {
        "component_id": "comp-foo",
        # Unique per run so no prior cache entry can turn this into a hit.
        "spec_bundle_hash": "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        "spec": "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "# Constraints\n\nNone.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "# Glossary\n\n- **Foo** — a test term.",
        "hint_code": None,
    }


def test_hanging_model_yields_single_attempt_and_model_call_error(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    # Keep any cache traffic local to this temporary repo.
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    call_log = tmp_path / "mock_calls.log"
    call_log.write_text("")

    def hanging_backend(prompt, model, **params):
        # Record the attempt first, so a retry would show up as a second line.
        with open(call_log, "a") as fh:
            fh.write("call\n")
        # The provider never answers. Block briefly, then report what the
        # SDK reports when its own default timeout expires.
        time.sleep(0.2)
        return {
            "text": None,
            "model": model,
            "backend": "mock-hang",
            "model_call_error": {
                "category": "timeout",
                "message": "model call timed out",
            },
        }

    outcome = {}

    def run():
        try:
            outcome["result"] = generator.generate(
                _bundle(),
                "claude-sonnet-5",
                repo_root=repo_root,
                llm_backend=hanging_backend,
            )
        except BaseException as exc:  # surfaced below
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout=120)

    assert not worker.is_alive(), "generate did not complete: unbounded hang"
    assert "error" not in outcome, "generate raised instead of returning: %r" % (
        outcome.get("error"),
    )

    result = outcome["result"]

    # The call completed with model_call_error set.
    assert field(result, "model_call_error"), "expected model_call_error to be set"
    assert not field(result, "files"), "a failed call must not produce files"
    assert field(result, "refused") is None, "a hang is a model_call_error, not a refusal"
    assert field(result, "cache_hit") is False

    # Exactly one call attempt: no internal retry.
    lines = [ln for ln in call_log.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1, "expected exactly one model call attempt, saw %d" % len(lines)