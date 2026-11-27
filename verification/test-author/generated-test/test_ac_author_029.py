# hotdocs-criterion: sha256:6df131c7eb63e0b2f6b33c1f42347e8dc719ff7b224afd39e1b70efcda69b7b7
import dataclasses
import json

import pytest

import test_author


FIXED_BUNDLE = {
    "component_id": "comp-foo",
    "criterion_id": "AC-FOO-001",
    "covers": "R-FOO-001",
    "criterion_text": "Given x When y Then z",
    "requirement_text": "R-FOO-001 text",
    "interface": "foo() -> None",
    "glossary": "",
    "dependency_interfaces": {},
    "testing": "",
}


@dataclasses.dataclass
class StubResult:
    component_id: str
    criterion_id: str
    model: str
    seed: int
    prompt_version: str
    cache_hit: bool
    file: object
    model_call_error: object
    repair_attempts: int
    probe_findings: list

    def __getitem__(self, name):
        return getattr(self, name)

    def get(self, name, default=None):
        return getattr(self, name, default)

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_root(tmp_path, name):
    root = tmp_path / name
    base = root / "gen" / "spec-bundle-assembler"
    base.mkdir(parents=True)
    source = (
        "FIXED = " + repr(FIXED_BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(FIXED)\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode=" + repr("cold") + "):\n"
        "    raise RuntimeError(" + repr("not used") + ")\n"
    )
    (base / "spec_bundle_assembler.py").write_text(source, encoding="utf-8")
    return root


def install_stub(monkeypatch, model_call_error):
    calls = []

    def stub(bundle, model, seed=0, *args, repo_root=None, llm_backend=None, **kwargs):
        if args:
            seed = args[0] if not isinstance(seed, int) else seed
        calls.append({"bundle": bundle, "model": model, "seed": seed, "repo_root": repo_root})
        return StubResult(
            component_id="comp-foo",
            criterion_id="AC-FOO-001",
            model=model,
            seed=seed,
            prompt_version="v1",
            cache_hit=False,
            file={"path": "p.py", "content": "x"},
            model_call_error=model_call_error,
            repair_attempts=0,
            probe_findings=[],
        )

    monkeypatch.setattr(test_author, "author_test", stub)
    return calls


def valid_argv(root):
    return ["comp-foo", "AC-FOO-001", "--model", "m", "--repo-root", str(root)]


def test_text_success_returns_0_and_uses_seed_0(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, "text_ok")
    monkeypatch.chdir(root)
    calls = install_stub(monkeypatch, None)
    capsys.readouterr()

    code = test_author.main(valid_argv(root))
    out = capsys.readouterr()

    assert code == 0
    assert out.out == "AC-FOO-001: wrote p.py\n"
    assert len(calls) == 1
    assert calls[0]["seed"] == 0


def test_json_format_prints_result_json(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, "json_ok")
    monkeypatch.chdir(root)
    install_stub(monkeypatch, None)
    capsys.readouterr()

    code = test_author.main(valid_argv(root) + ["--format=json"])
    out = capsys.readouterr()

    assert code == 0
    doc = json.loads(out.out)
    assert field(doc, "criterion_id") == "AC-FOO-001"


def test_model_call_error_returns_1(tmp_path, monkeypatch, capsys):
    root = make_root(tmp_path, "error")
    monkeypatch.chdir(root)
    install_stub(monkeypatch, {"category": "network", "message": "down"})
    capsys.readouterr()

    code = test_author.main(valid_argv(root))
    out = capsys.readouterr()

    assert code == 1
    assert out.out == "AC-FOO-001: model_call_error network: down\n"


@pytest.mark.parametrize(
    "case, extra, cause",
    [
        ("one_positional", None, "expected <component-id> and <criterion-id>"),
        ("bad_format", ["--format=xml"], "--format must be json or text"),
        ("bad_seed", ["--seed=x"], "--seed must be an integer"),
        ("unknown", ["--bogus"], "unknown argument --bogus"),
        ("final_model", ["--model"], "--model requires a value"),
    ],
)
def test_usage_errors_return_2(tmp_path, monkeypatch, capsys, case, extra, cause):
    root = make_root(tmp_path, "usage_" + case)
    monkeypatch.chdir(root)
    install_stub(monkeypatch, None)
    capsys.readouterr()

    if extra is None:
        argv = ["comp-foo"]
    else:
        argv = valid_argv(root) + extra

    code = test_author.main(argv)
    out = capsys.readouterr()

    assert code == 2
    assert out.out == ""
    assert out.err.startswith("usage error: " + cause)