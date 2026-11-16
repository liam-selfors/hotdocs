import json
import re

import test_author


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_bundle():
    # Deliberately avoid the words "last_ratified_commit" anywhere in the
    # bundle, so any mention in the prompt must come from author_test itself.
    criterion_text = (
        "Given a synthetic spec corpus fixture under a fresh temporary repo_root,\n"
        "  containing specs/components/foo/component.md and a decision document\n"
        "  specs/decisions/D1.md\n"
        "When foo(x) is called with x = 2\n"
        "Then it returns 4"
    )
    requirement_text = (
        "# R-FOO-001\n\n"
        "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`."
    )
    interface = "# Library\n\n```\nfoo(x: int) -> int\n```"
    glossary = "# Glossary\n\n- **Foo** \u2014 a test term."
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=criterion_text,
        requirement_text=requirement_text,
        interface=interface,
        glossary=glossary,
        dependency_interfaces={},
        module_names=["foo"],
    )


def test_prompt_states_ratified_requires_placeholder_last_ratified_commit(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    prompt_log = tmp_path / "prompts.jsonl"
    nonce_re = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

    def backend(prompt, model, **params):
        with open(prompt_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        nonces = nonce_re.findall(prompt)
        nonce = nonces[-1] if nonces else "0" * 32
        body = "def test_foo():\n    assert 2 * 2 == 4\n"
        text = "-----BEGIN FILE %s-----\n%s-----END FILE %s-----\n" % (nonce, body, nonce)
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _make_bundle()
    result = test_author.author_test(
        bundle,
        "mock:ac-author-018-fixture-model",
        seed=18018,
        repo_root=repo_root,
        llm_backend=backend,
    )
    assert result is not None

    assert prompt_log.is_file(), "the mock backend was never called, so no prompt was built"
    records = [
        json.loads(line)
        for line in prompt_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records, "no prompt captured"

    for record in records:
        prompt = record["prompt"]
        assert isinstance(prompt, str) and prompt

        indices = [m.start() for m in re.finditer(r"last_ratified_commit", prompt)]
        assert indices, "prompt never mentions last_ratified_commit"

        found = False
        for i in indices:
            window = prompt[max(0, i - 600): i + 600].lower()
            mentions_ratified = "ratified" in window.replace("last_ratified_commit", "")
            mentions_status = "status" in window
            mentions_placeholder = "placeholder" in window or "fake" in window
            if mentions_ratified and mentions_status and mentions_placeholder:
                found = True
                break
        assert found, (
            "prompt does not state that a document with status: ratified must also "
            "set last_ratified_commit to a placeholder value"
        )

    error = _field(result, "model_call_error")
    assert error is None, "unexpected model_call_error: %r" % (error,)